"""
Custom TTS Provider for local ONNX/PyTorch models.

This provider allows loading TTS models from local paths, supporting
both ONNX runtime and PyTorch models. It's designed for:
- Custom fine-tuned models
- Models not available through standard packages
- Offline/airgapped deployments
- Vibe Voice and similar custom models

Features:
- Load ONNX models for optimized inference
- Load PyTorch models (state_dict or full model)
- Configurable sample rate and audio format
- Optional voice cloning if model supports it
- HuggingFace model loading support

Usage:
    from app.voice.providers.tts_custom import CustomTTSProvider
    from app.voice.providers.base import TTSConfig

    # Load ONNX model
    config = TTSConfig(model_path="/path/to/model.onnx")
    provider = CustomTTSProvider(config, config_path="/path/to/config.json")
    await provider.initialize()

    # Load PyTorch model
    config = TTSConfig(model_path="/path/to/model.pt")
    provider = CustomTTSProvider(config)

    # Load from HuggingFace
    provider = CustomTTSProvider.from_huggingface("username/model-name")

    # Synthesize
    audio = await provider.synthesize("Hello world!")
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import AsyncIterator, List, Optional, Dict, Any, Union, Callable

from app.voice.providers.base import TTSProvider, TTSConfig, TTSProviderError

logger = logging.getLogger(__name__)


class CustomTTSProvider(TTSProvider):
    """
    Custom TTS provider for loading local ONNX or PyTorch models.

    Supports various model formats and architectures, allowing
    integration of custom or fine-tuned TTS models.
    """

    def __init__(
        self,
        config: Optional[TTSConfig] = None,
        config_path: Optional[str] = None,
        model_class: Optional[type] = None,
        preprocessor: Optional[Callable[[str], Any]] = None,
        postprocessor: Optional[Callable[[Any], bytes]] = None,
    ):
        """
        Initialize the Custom TTS provider.

        Args:
            config: TTSConfig with model_path set
            config_path: Path to model config JSON file
            model_class: Optional PyTorch model class for loading state_dict
            preprocessor: Optional function to preprocess text before model
            postprocessor: Optional function to convert model output to audio bytes
        """
        super().__init__(config)
        self._config_path = config_path
        self._model_class = model_class
        self._preprocessor = preprocessor
        self._postprocessor = postprocessor

        self._model = None
        self._model_config: Dict[str, Any] = {}
        self._is_onnx = False
        self._tokenizer = None
        self._cloned_voices: Dict[str, Any] = {}

    async def initialize(self) -> None:
        """Load the model from the configured path."""
        if self._initialized:
            return

        model_path = self.config.model_path
        if not model_path:
            raise TTSProviderError(
                "No model path specified. Set config.model_path",
                provider=self.name,
            )

        model_path = Path(model_path)
        if not model_path.exists():
            raise TTSProviderError(
                f"Model not found: {model_path}",
                provider=self.name,
            )

        try:
            # Load config if provided
            if self._config_path:
                await self._load_config(self._config_path)

            # Determine model type and load
            if model_path.suffix in (".onnx",):
                await self._load_onnx(model_path)
            elif model_path.suffix in (".pt", ".pth", ".bin"):
                await self._load_pytorch(model_path)
            elif model_path.is_dir():
                # Directory - might be HuggingFace format
                await self._load_hf_directory(model_path)
            else:
                raise TTSProviderError(
                    f"Unsupported model format: {model_path.suffix}",
                    provider=self.name,
                )

            self._initialized = True
            logger.info(f"Loaded custom TTS model from {model_path}")

        except TTSProviderError:
            raise
        except Exception as e:
            raise TTSProviderError(
                f"Failed to load model: {e}",
                provider=self.name,
                cause=e,
            )

    async def _load_config(self, config_path: str) -> None:
        """Load model configuration from JSON file."""
        config_path = Path(config_path)
        if config_path.exists():
            with open(config_path) as f:
                self._model_config = json.load(f)

            # Update provider config from model config
            if "sample_rate" in self._model_config:
                self.config.sample_rate = self._model_config["sample_rate"]
            if "voices" in self._model_config:
                self._model_config["available_voices"] = self._model_config["voices"]

            logger.info(f"Loaded model config from {config_path}")

    async def _load_onnx(self, model_path: Path) -> None:
        """Load ONNX model."""
        try:
            import onnxruntime as ort

            # Create session with optimizations
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            # Select execution provider
            providers = ["CPUExecutionProvider"]

            device = self.config.device
            if device == "auto":
                from app.voice.providers.base import detect_device
                device = detect_device()

            if device == "cuda":
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            elif device == "mps":
                providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]

            self._model = ort.InferenceSession(
                str(model_path),
                sess_options=sess_options,
                providers=providers,
            )
            self._is_onnx = True

            # Get model metadata
            self._model_config.update({
                "inputs": [inp.name for inp in self._model.get_inputs()],
                "outputs": [out.name for out in self._model.get_outputs()],
            })

            logger.info(f"Loaded ONNX model with providers: {providers}")

        except ImportError as e:
            raise TTSProviderError(
                "ONNX Runtime not installed. Install with: pip install onnxruntime",
                provider=self.name,
                cause=e,
            )

    async def _load_pytorch(self, model_path: Path) -> None:
        """Load PyTorch model."""
        try:
            import torch

            device = self.config.device
            if device == "auto":
                from app.voice.providers.base import detect_device
                device = detect_device()
                if device == "mlx":
                    device = "cpu"

            # Load model
            if self._model_class:
                # Instantiate model class and load state dict
                model_config = self._model_config.get("model_config", {})
                self._model = self._model_class(**model_config)
                state_dict = torch.load(model_path, map_location=device)
                self._model.load_state_dict(state_dict)
            else:
                # Load full model
                self._model = torch.load(model_path, map_location=device)

            self._model.eval()
            self._is_onnx = False

            logger.info(f"Loaded PyTorch model on {device}")

        except ImportError as e:
            raise TTSProviderError(
                "PyTorch not installed. Install with: pip install torch",
                provider=self.name,
                cause=e,
            )

    async def _load_hf_directory(self, model_path: Path) -> None:
        """Load model from HuggingFace-style directory."""
        try:
            # Check for ONNX model
            onnx_path = model_path / "model.onnx"
            if onnx_path.exists():
                await self._load_onnx(onnx_path)
                return

            # Check for PyTorch model
            for pt_name in ["pytorch_model.bin", "model.pt", "model.pth"]:
                pt_path = model_path / pt_name
                if pt_path.exists():
                    await self._load_pytorch(pt_path)
                    return

            # Try loading with transformers
            try:
                from transformers import AutoModel, AutoTokenizer

                self._model = AutoModel.from_pretrained(str(model_path))
                self._tokenizer = AutoTokenizer.from_pretrained(str(model_path))
                self._is_onnx = False
                return
            except Exception:
                pass

            raise TTSProviderError(
                f"No supported model found in directory: {model_path}",
                provider=self.name,
            )

        except TTSProviderError:
            raise
        except Exception as e:
            raise TTSProviderError(
                f"Failed to load model directory: {e}",
                provider=self.name,
                cause=e,
            )

    @classmethod
    async def from_huggingface(
        cls,
        repo_id: str,
        revision: Optional[str] = None,
        config: Optional[TTSConfig] = None,
    ) -> "CustomTTSProvider":
        """
        Load a TTS model from HuggingFace Hub.

        Args:
            repo_id: HuggingFace repository ID (e.g., "username/model-name")
            revision: Git revision to use
            config: Optional TTSConfig

        Returns:
            Initialized CustomTTSProvider
        """
        try:
            from huggingface_hub import snapshot_download

            # Download model
            model_path = snapshot_download(
                repo_id,
                revision=revision,
            )

            # Create config
            config = config or TTSConfig()
            config.model_path = model_path

            # Create and initialize provider
            provider = cls(config)
            await provider.initialize()

            return provider

        except ImportError as e:
            raise TTSProviderError(
                "huggingface_hub not installed. Install with: pip install huggingface_hub",
                cause=e,
            )

    async def cleanup(self) -> None:
        """Clean up model resources."""
        self._model = None
        self._tokenizer = None
        self._cloned_voices.clear()
        self._initialized = False

    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        """
        Synthesize speech from text.

        Args:
            text: The text to synthesize
            voice: Optional voice ID

        Returns:
            PCM audio bytes
        """
        if not self._initialized:
            await self.initialize()

        try:
            loop = asyncio.get_event_loop()

            audio = await loop.run_in_executor(
                None,
                lambda: self._synthesize_internal(text, voice),
            )

            return audio

        except Exception as e:
            raise TTSProviderError(
                f"Synthesis failed: {e}",
                provider=self.name,
                cause=e,
            )

    def _synthesize_internal(self, text: str, voice: Optional[str]) -> bytes:
        """Internal synthesis method."""
        import numpy as np

        # Preprocess text
        if self._preprocessor:
            inputs = self._preprocessor(text)
        elif self._tokenizer:
            inputs = self._tokenizer(text, return_tensors="pt" if not self._is_onnx else "np")
        else:
            # Default preprocessing - convert to character IDs
            inputs = self._default_preprocess(text)

        # Run inference
        if self._is_onnx:
            audio = self._run_onnx(inputs, voice)
        else:
            audio = self._run_pytorch(inputs, voice)

        # Postprocess
        if self._postprocessor:
            return self._postprocessor(audio)

        # Default postprocessing - convert to int16 PCM
        if hasattr(audio, "numpy"):
            audio = audio.numpy()
        elif hasattr(audio, "cpu"):
            audio = audio.cpu().numpy()

        if len(audio.shape) > 1:
            audio = audio.flatten()

        # Normalize if needed
        if audio.max() > 1.0 or audio.min() < -1.0:
            audio = audio / max(abs(audio.max()), abs(audio.min()))

        audio_int16 = (audio * 32767).astype(np.int16)
        return audio_int16.tobytes()

    def _default_preprocess(self, text: str) -> Any:
        """Default text preprocessing."""
        import numpy as np

        # Simple character-level encoding
        chars = list(text.lower())
        # Basic ASCII mapping
        char_ids = [ord(c) - 32 for c in chars if 32 <= ord(c) < 128]
        return np.array([char_ids], dtype=np.int64)

    def _run_onnx(self, inputs: Any, voice: Optional[str]) -> Any:
        """Run ONNX inference."""
        import numpy as np

        # Prepare inputs
        input_names = self._model_config.get("inputs", [])
        output_names = self._model_config.get("outputs", [])

        if isinstance(inputs, dict):
            feed_dict = {k: v.numpy() if hasattr(v, "numpy") else v for k, v in inputs.items()}
        else:
            # Assume single input
            input_name = input_names[0] if input_names else "input"
            feed_dict = {input_name: inputs if isinstance(inputs, np.ndarray) else np.array(inputs)}

        # Add voice embedding if available
        if voice and voice in self._cloned_voices:
            embedding = self._cloned_voices[voice]
            feed_dict["speaker_embedding"] = embedding

        # Run inference
        outputs = self._model.run(output_names or None, feed_dict)

        return outputs[0] if outputs else np.array([])

    def _run_pytorch(self, inputs: Any, voice: Optional[str]) -> Any:
        """Run PyTorch inference."""
        import torch

        with torch.no_grad():
            # Prepare inputs
            if isinstance(inputs, dict):
                model_inputs = {k: torch.tensor(v) if not isinstance(v, torch.Tensor) else v
                               for k, v in inputs.items()}

                # Add voice embedding
                if voice and voice in self._cloned_voices:
                    model_inputs["speaker_embedding"] = torch.tensor(self._cloned_voices[voice])

                outputs = self._model(**model_inputs)
            else:
                tensor_inputs = torch.tensor(inputs) if not isinstance(inputs, torch.Tensor) else inputs
                outputs = self._model(tensor_inputs)

            # Extract audio from outputs
            if isinstance(outputs, dict):
                audio = outputs.get("audio", outputs.get("wav", outputs.get("output")))
            elif isinstance(outputs, (list, tuple)):
                audio = outputs[0]
            else:
                audio = outputs

            return audio

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """
        Stream synthesized speech.

        Note: Most custom models don't support true streaming,
        so this simulates streaming by chunking the output.

        Args:
            text: The text to synthesize
            voice: Optional voice ID

        Yields:
            Audio chunks (PCM bytes)
        """
        audio = await self.synthesize(text, voice)

        # Yield in chunks
        chunk_samples = int(self.config.sample_rate * 0.02)
        chunk_bytes = chunk_samples * 2

        for i in range(0, len(audio), chunk_bytes):
            chunk = audio[i:i + chunk_bytes]
            if chunk:
                yield chunk
                await asyncio.sleep(0.01)

    async def clone_voice(
        self,
        audio_sample: Union[bytes, str, Path],
        voice_name: Optional[str] = None,
    ) -> str:
        """
        Clone a voice if the model supports it.

        Args:
            audio_sample: Audio sample for cloning
            voice_name: Optional name for the voice

        Returns:
            Voice ID

        Raises:
            NotImplementedError: If model doesn't support cloning
        """
        if not self._model_config.get("supports_voice_cloning", False):
            raise NotImplementedError(
                f"{self.name} model does not support voice cloning"
            )

        import uuid
        voice_id = voice_name or f"custom_{uuid.uuid4().hex[:8]}"

        # This is a placeholder - actual implementation depends on model
        # Most models require extracting a speaker embedding
        logger.warning(
            "Voice cloning for custom models requires model-specific implementation"
        )

        self._cloned_voices[voice_id] = None
        return voice_id

    @property
    def name(self) -> str:
        """Provider name."""
        model_name = self._model_config.get("name", "custom")
        return f"custom-{model_name}"

    @property
    def available_voices(self) -> List[str]:
        """List of available voice IDs."""
        voices = self._model_config.get("available_voices", ["default"])
        voices.extend(self._cloned_voices.keys())
        return voices

    @property
    def sample_rate(self) -> int:
        """Audio sample rate."""
        return self.config.sample_rate

    @property
    def supports_voice_cloning(self) -> bool:
        """Whether this model supports voice cloning."""
        return self._model_config.get("supports_voice_cloning", False)

    @property
    def supports_streaming(self) -> bool:
        """Streaming is simulated for custom models."""
        return True

    def get_voice_info(self, voice_id: str) -> Dict[str, Any]:
        """Get information about a voice."""
        voice_config = self._model_config.get("voice_config", {})
        if voice_id in voice_config:
            info = voice_config[voice_id].copy()
            info["id"] = voice_id
            return info
        return {"id": voice_id, "name": voice_id}
