import os
import re
import subprocess
import glob
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("OzoneDebugger")

@mcp.tool()
def generate_for_board(project_dir: str, board_name: str, template_jdebug: str = None, device: str = None, use_bash: bool = True) -> str:
    """
    Build firmware and generate .jdebug configuration for a specific target board.
    
    Args:
        project_dir: Root directory of the project.
        board_name: Target board name (e.g., 'nRF52840', 'STM32F407').
        template_jdebug: (Optional) Template .jdebug file path. If not provided, will search for one.
        device: (Optional) Device model for SetDevice. If not provided, derived from board_name.
        use_bash: (Optional) Use bash shell for build command (default: True).
    
    Returns:
        Status message with generated file paths or error details.
    """
    try:
        orig_dir = os.getcwd()
        os.chdir(project_dir)
        
        # 1. Build for specific board using Makefile variable
        build_cmd = f"make BOARD={board_name} clean && make BOARD={board_name}"
        
        # Execute with bash if requested
        if use_bash:
            build_result = subprocess.run(build_cmd, shell=True, executable='/bin/bash', capture_output=True, text=True, timeout=300)
        else:
            build_result = subprocess.run(build_cmd, shell=True, capture_output=True, text=True, timeout=300)
        
        if build_result.returncode != 0:
            os.chdir(orig_dir)
            return f"Build failed for {board_name}!\n--- Output ---\n{build_result.stdout}\n--- Error ---\n{build_result.stderr}"
        
        # 2. Find generated ELF file
        elf_pattern = "**/*.elf"
        elf_files = glob.glob(os.path.join(project_dir, elf_pattern), recursive=True)
        
        if not elf_files:
            os.chdir(orig_dir)
            return f"Error: No ELF file found after building for {board_name}"
        
        elf_path = elf_files[0]
        print(f"Generated ELF: {elf_path}")
        
        # 3. Generate or locate .jdebug file
        if template_jdebug is None:
            # Auto-search for template
            jdebug_candidates = glob.glob(os.path.join(project_dir, "**/*.jdebug"), recursive=True)
            if not jdebug_candidates:
                os.chdir(orig_dir)
                return f"Error: No .jdebug template found. Please provide template_jdebug parameter."
            template_jdebug = jdebug_candidates[0]
        
        # Create board-specific .jdebug file
        jdebug_output = os.path.join(project_dir, f"{board_name}.jdebug")
        
        with open(template_jdebug, 'r', encoding='utf-8') as f:
            jdebug_content = f.read()
        
        # Update ELF path in .jdebug
        jdebug_content = re.sub(
            r'(Project\.AddElf\s*\(")(.*?)("\);)',
            fr'\1{elf_path}\3',
            jdebug_content
        )
        
        # Update device if provided
        if device:
            jdebug_content = re.sub(
                r'(Project\.SetDevice\s*\(")(.*?)("\);)',
                fr'\1{device}\3',
                jdebug_content
            )
        
        with open(jdebug_output, 'w', encoding='utf-8') as f:
            f.write(jdebug_content)
        
        os.chdir(orig_dir)
        
        return f"Success! Generated files for {board_name}:\n" \
               f"- ELF: {elf_path}\n" \
               f"- JDEBUG: {jdebug_output}"
    
    except Exception as e:
        os.chdir(orig_dir)
        return f"Exception occurred in generate_for_board: {str(e)}"

@mcp.tool()
def patch_and_run_ozone(jdebug_path: str, new_elf_path: str, device: str = None, use_bash: bool = True) -> str:
    """
    Modify the .jdebug project file and execute flashing/debugging tasks.
    
    Args:
        jdebug_path: Path to the .jdebug file.
        new_elf_path: Path to the new compiled artifact (.elf).
        device: (Optional) Device model, such as 'nRF52840_XXAA'.
        use_bash: (Optional) Use bash shell to invoke Ozone (default: True).
    
    Note: You must build the firmware first to generate the .elf file before using this tool.
    """
    if not os.path.exists(new_elf_path):
        return f"Error: ELF file not found at {new_elf_path}. Please run 'make' or your build command first to generate the .elf file."
    
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
        if use_bash:
            cmd = f'Ozone -project "{jdebug_path}" -minimized -exit'
            result = subprocess.run(cmd, shell=True, executable='/bin/bash', capture_output=True, text=True, timeout=60)
        else:
            args = ["Ozone", "-project", jdebug_path, "-minimized", "-exit"]
            result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        
        response = f"Project has been updated and attempted to run.\n--- Console Log ---\n{result.stdout}"
        if result.stderr:
            response += f"\n--- Error Feedback ---\n{result.stderr}"
        return response

    except Exception as e:
        return f"Exception occurred during processing: {str(e)}"

if __name__ == "__main__":
    mcp.run()