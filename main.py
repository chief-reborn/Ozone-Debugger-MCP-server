import os
import re
import subprocess
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("OzoneDebugger")

@mcp.tool()
def patch_and_run_ozone(jdebug_path: str, new_elf_path: str, device: str = None) -> str:
    """
    Modify the .jdebug project file and execute flashing/debugging tasks.
    
    Args:
        jdebug_path: Path to the .jdebug file.
        new_elf_path: Path to the new compiled artifact (.elf).
        device: (Optional) Device model, such as 'nRF52840_XXAA'.
    """
    if not os.path.exists(jdebug_path):
        return f"Error: Project file not found {jdebug_path}"

    try:
        # 1. Read and modify the .jdebug file
        with open(jdebug_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Modify ELF path: match Project.AddElf("...");
        # Use regex to ensure replacement within quotes
        content = re.sub(
            r'(Project\.AddElf\s*\(")(.*?)("\);)',
            fr'\1{new_elf_path}\3',
            content
        )

        # If device model is provided, modify Project.SetDevice("...");
        if device:
            content = re.sub(
                r'(Project\.SetDevice\s*\(")(.*?)("\);)',
                fr'\1{device}\3',
                content
            )

        # 2. Write back to file
        with open(jdebug_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # 3. Start command line execution
        # -minimized: minimized run
        # -exit: automatically exit after task completion
        args = ["Ozone", "-project", jdebug_path, "-minimized", "-exit"]
        
        # Capture output for AI log analysis
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        
        response = f"Project has been updated and attempted to run.\n--- Console Log ---\n{result.stdout}"
        if result.stderr:
            response += f"\n--- Error Feedback ---\n{result.stderr}"
        return response

    except Exception as e:
        return f"Exception occurred during processing: {str(e)}"

if __name__ == "__main__":
    mcp.run()