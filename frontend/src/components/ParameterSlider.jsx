import { useState } from 'react';

const ParameterSlider = ({
  label,
  value,
  onChange,
  min = 0,
  max = 1,
  step = 0.1,
  description,
  leftLabel,
  rightLabel,
  disabled = false
}) => {
  const [showTooltip, setShowTooltip] = useState(false);

  const percentage = ((value - min) / (max - min)) * 100;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-slate-300">{label}</label>
        <span className="text-sm font-mono text-unicorn-400">{value.toFixed(step < 1 ? 1 : 0)}</span>
      </div>

      <div className="relative">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
          disabled={disabled}
          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer slider-thumb disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            background: `linear-gradient(to right, rgb(139, 92, 246) 0%, rgb(139, 92, 246) ${percentage}%, rgb(51, 65, 85) ${percentage}%, rgb(51, 65, 85) 100%)`
          }}
        />
      </div>

      {(leftLabel || rightLabel) && (
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>{leftLabel}</span>
          <span>{rightLabel}</span>
        </div>
      )}

      {description && (
        <p className="text-xs text-slate-400 leading-relaxed">{description}</p>
      )}

      <style jsx>{`
        .slider-thumb::-webkit-slider-thumb {
          appearance: none;
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: linear-gradient(135deg, rgb(139, 92, 246), rgb(6, 182, 212));
          cursor: pointer;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
          transition: transform 0.2s;
        }

        .slider-thumb::-webkit-slider-thumb:hover {
          transform: scale(1.1);
        }

        .slider-thumb::-moz-range-thumb {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: linear-gradient(135deg, rgb(139, 92, 246), rgb(6, 182, 212));
          cursor: pointer;
          border: none;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
          transition: transform 0.2s;
        }

        .slider-thumb::-moz-range-thumb:hover {
          transform: scale(1.1);
        }
      `}</style>
    </div>
  );
};

export default ParameterSlider;
