import os
import re
import subprocess
import shutil
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("OzoneDebugger")

def get_bash_executable():
    """Find bash executable with multiple fallback strategies for different OS."""
    # First try standard PATH
    bash_in_path = shutil.which('bash')
    if bash_in_path:
        return bash_in_path
    
    # Windows-specific: Try common Git Bash locations
    if os.name == 'nt':  # Windows
        git_bash_paths = [
            os.path.expandvars(r'%ProgramFiles%\Git\bin\bash.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Git\bin\bash.exe'),
            os.path.expandvars(r'%LocalAppData%\Programs\Git\bin\bash.exe'),
        ]
        for path in git_bash_paths:
            if os.path.exists(path):
                return path
        
        # Try to find Git and infer bash location
        git_exe = shutil.which('git')
        if git_exe:
            git_dir = os.path.dirname(os.path.dirname(git_exe))
            bash_path = os.path.join(git_dir, 'bin', 'bash.exe')
            if os.path.exists(bash_path):
                return bash_path
    
    return None

def normalize_path(path: str) -> str:
    """Normalize path separators and convert to absolute path."""
    return os.path.normpath(os.path.abspath(path))

@mcp.tool()
def update_jdebug(
    jdebug_path: str,
    elf_path: str = None,
    device: str = None,
    debugger: str = None,
    output_path: str = None
) -> str:
    """
    Update .jdebug project file settings.
    
    Args:
        jdebug_path: Path to the .jdebug file.
        elf_path: (Optional) New firmware file path (.out or .elf).
        device: (Optional) Device model (e.g., 'nRF52840_XXAA', 'STM32F407VG').
        debugger: (Optional) Debugger model (e.g., 'JLink', 'ST-Link').
        output_path: (Optional) Save modified .jdebug to this path. If None, updates original file.
    
    Returns:
        Status message with updated configuration or error details.
    """
    # Normalize paths
    jdebug_path = normalize_path(jdebug_path)
    
    if not os.path.exists(jdebug_path):
        return f"Error: .jdebug file not found at {jdebug_path}"
    
    try:
        # Read the original file
        with open(jdebug_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        
        # Update firmware file path (supports .out and .elf)
        if elf_path:
            # Normalize the firmware path
            elf_path = normalize_path(elf_path)
            
            # Check if file exists
            if not os.path.exists(elf_path):
                return f"Error: Firmware file not found at {elf_path}"
            
            # Use forward slashes for consistency inside .jdebug
            elf_path_normalized = elf_path.replace(os.sep, '/')
            
            # Find and replace using regex to locate, then string replace to avoid special char issues
            pattern = r'Project\.AddElf\s*\("([^"]+)"\);'
            match = re.search(pattern, content)
            if match:
                old_line = match.group(0)
                new_line = f'Project.AddElf("{elf_path_normalized}");'
                content = content.replace(old_line, new_line, 1)
                modified = True
        
        # Update device if provided
        if device:
            pattern = r'Project\.SetDevice\s*\("([^"]+)"\);'
            match = re.search(pattern, content)
            if match:
                old_line = match.group(0)
                new_line = f'Project.SetDevice("{device}");'
                content = content.replace(old_line, new_line, 1)
                modified = True
        
        # Update debugger if provided
        if debugger:
            pattern = r'Project\.SetDebugger\s*\("([^"]+)"\);'
            match = re.search(pattern, content)
            if match:
                old_line = match.group(0)
                new_line = f'Project.SetDebugger("{debugger}");'
                content = content.replace(old_line, new_line, 1)
                modified = True
        
        if not modified:
            return f"Warning: No matching configuration found in {jdebug_path}"
        
        # Write to output file
        target_path = normalize_path(output_path) if output_path else jdebug_path
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        summary = f"Successfully updated .jdebug configuration.\nSaved to: {target_path}\n"
        if elf_path:
            summary += f"- Firmware: {elf_path}\n"
        if device:
            summary += f"- Device: {device}\n"
        if debugger:
            summary += f"- Debugger: {debugger}\n"
        
        return summary
    
    except Exception as e:
        return f"Error updating .jdebug: {str(e)}"

@mcp.tool()
def flash_with_ozone(jdebug_path: str, use_bash: bool = True) -> str:
    """
    Flash firmware using SEGGER Ozone with the specified .jdebug project.
    
    Args:
        jdebug_path: Path to the .jdebug project file.
        use_bash: (Optional) Use bash shell to invoke Ozone (default: True).
    
    Returns:
        Status message with Ozone output or error details.
    """
    # Normalize path
    jdebug_path = normalize_path(jdebug_path)
    
    if not os.path.exists(jdebug_path):
        return f"Error: .jdebug file not found at {jdebug_path}"
    
    try:
        # Prepare Ozone command
        # -minimized: run in minimized mode
        # -exit: exit automatically after completion
        
        if use_bash:
            bash_exec = get_bash_executable()
            if not bash_exec:
                return "Error: bash not found. Try use_bash=False to use system shell."
            cmd = f'Ozone -project "{jdebug_path}" -minimized -exit'
            result = subprocess.run(cmd, shell=True, executable=bash_exec, capture_output=True, text=True, timeout=120)
        else:
            args = ["Ozone", "-project", jdebug_path, "-minimized", "-exit"]
            result = subprocess.run(args, capture_output=True, text=True, timeout=120)
        
        response = f"Ozone execution completed.\n"
        response += f"Return code: {result.returncode}\n"
        
        if result.stdout:
            response += f"\n--- Console Output ---\n{result.stdout}"
        
        if result.stderr:
            response += f"\n--- Error Output ---\n{result.stderr}"
        
        return response
    
    except subprocess.TimeoutExpired:
        return "Error: Ozone execution timed out (exceeded 120 seconds)"
    except Exception as e:
        return f"Error executing Ozone: {str(e)}"

@mcp.tool()
def update_and_flash(
    jdebug_path: str,
    elf_path: str = None,
    device: str = None,
    debugger: str = None,
    use_bash: bool = True
) -> str:
    """
    Update .jdebug settings and immediately flash with Ozone.
    
    Args:
        jdebug_path: Path to the .jdebug file.
        elf_path: (Optional) New ELF firmware file path.
        device: (Optional) Device model (e.g., 'nRF52840_XXAA').
        debugger: (Optional) Debugger model.
        use_bash: (Optional) Use bash shell for Ozone (default: True).
    
    Returns:
        Combined status from update and flash operations.
    """
    # First update .jdebug
    update_result = update_jdebug(jdebug_path, elf_path, device, debugger)
    
    if "Error" in update_result:
        return update_result
    
    # Then flash
    flash_result = flash_with_ozone(jdebug_path, use_bash)
    
    return update_result + "\n" + flash_result

@mcp.tool()
def get_jdebug_info(jdebug_path: str) -> str:
    """
    Read and display current .jdebug configuration.
    
    Args:
        jdebug_path: Path to the .jdebug file.
    
    Returns:
        Extracted configuration values or error message.
    """
    # Normalize path
    jdebug_path = normalize_path(jdebug_path)
    
    if not os.path.exists(jdebug_path):
        return f"Error: .jdebug file not found at {jdebug_path}"
    
    try:
        with open(jdebug_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        info = f"Configuration from: {jdebug_path}\n\n"
        
        # Extract firmware file path (supports .out and .elf)
        elf_match = re.search(r'Project\.AddElf\s*\("([^"]+)"\)', content)
        if elf_match:
            info += f"Firmware: {elf_match.group(1)}\n"
        
        # Extract device
        device_match = re.search(r'Project\.SetDevice\s*\("([^"]+)"\)', content)
        if device_match:
            info += f"Device: {device_match.group(1)}\n"
        
        # Extract debugger
        debugger_match = re.search(r'Project\.SetDebugger\s*\("([^"]+)"\)', content)
        if debugger_match:
            info += f"Debugger: {debugger_match.group(1)}\n"
        
        return info if info != f"Configuration from: {jdebug_path}\n\n" else "No configuration found in .jdebug file"
    
    except Exception as e:
        return f"Error reading .jdebug: {str(e)}"

if __name__ == "__main__":
    mcp.run()