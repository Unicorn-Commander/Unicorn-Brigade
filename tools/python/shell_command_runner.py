"""
Shell Command Runner Tool

Provides agents with the ability to execute shell commands.

This is a powerful and potentially dangerous tool. It must be implemented
with a strong focus on security, including sandboxing, command validation,
and timeout enforcement to prevent malicious or runaway processes.

Access to this tool should be highly restricted.

Potential Functions:
- execute(command, timeout)
"""

import subprocess

class ShellCommandRunner:
    def execute(self, command: str, timeout: int = 60) -> dict:
        """
        Executes a shell command in a sandboxed environment.

        Returns a dictionary containing stdout, stderr, and the return code.
        """
        # In a real implementation, this would use a secure sandbox.
        # The following is a simplified and UNSAFE example.
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out."}
        except subprocess.CalledProcessError as e:
            return {
                "error": "Command failed.",
                "stdout": e.stdout,
                "stderr": e.stderr,
                "return_code": e.returncode
            }
