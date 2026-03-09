import os
import subprocess
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("OzoneDebugger")

OZONE_CL_PATH = r"C:\Program Files\SEGGER\Ozone\OzoneConsole.exe"

@mcp.tool()
def run_ozone_cli(project_path: str, script_path: str = "", exit_after: bool = True) -> str:
    """
    Run Ozone Debugger via Command Line Interface for automated tasks.

    Args:
        project_path (str): The path to the Ozone project file (.jdebug).
        script_path (str, optional): Path to a script file to execute commands.
        exit_after (bool): Whether to close Ozone after the execution is finished.
    """
    if not os.path.exists(OZONE_CL_PATH):
        return f"Ozone Console not found at: {OZONE_CL_PATH}"

    if not os.path.exists(project_path):
        return "Project path does not exist."

    args = [OZONE_CL_PATH, "-project", project_path, "-minimized"]

    if script_path:
        if os.path.exists(script_path):
            args.extend(["-exec", f"source(\"{script_path}\")"])
        else:
            return f"Script path does not exist: {script_path}"

    if exit_after:
        args.append("-exit")

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        
        log_output = f"--- Ozone CLI Output ---\n{result.stdout}"
        if result.stderr:
            log_output += f"\n--- Errors ---\n{result.stderr}"
            
        return log_output
    except subprocess.TimeoutExpired:
        return "Error: Ozone execution timed out."
    except Exception as e:
        return f"Failed to execute Ozone CLI: {str(e)}"

if __name__ == "__main__":
    mcp.run()