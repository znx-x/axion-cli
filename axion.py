import os
import sys
import time
import json
import configparser
import requests
import argparse
from datetime import datetime
from typing import List, Dict, Generator, Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich import box
from rich.prompt import Prompt

# Import Tools
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from tools.search_tool import SearchTool
    from tools.fetch_tool import FetchTool
except ImportError:
    pass # Handle case where tools aren't set up yet

# --- Setup Constants ---
CONFIG_FILE = 'config.ini'
CONVERSATIONS_DIR = 'conversations'
os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

console = Console()

# --- Visual Styles ---
AXION_BLUE = "dodger_blue1"
AXION_PURPLE = "medium_purple1"
USER_COLOR = "green"
AI_COLOR = "bright_white"

# --- Config Loader ---
def load_config():
    if getattr(sys, 'frozen', False):
        app_path = os.path.dirname(sys.executable)
    else:
        app_path = os.path.dirname(os.path.abspath(__file__))
    
    config_path = os.path.join(app_path, CONFIG_FILE)
    config = configparser.ConfigParser()
    
    if not os.path.exists(config_path):
        console.print(f"[bold red]Error:[/bold red] {CONFIG_FILE} not found.")
        sys.exit(1)
    config.read(config_path)
    return config

# --- Logging Manager ---
class LogManager:
    def __init__(self, session_id=None):
        if session_id:
            # Clean up the ID if user typed ".json"
            session_id = session_id.replace('.json', '')
            self.filename = os.path.join(CONVERSATIONS_DIR, f"{session_id}.json")
        else:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            self.filename = os.path.join(CONVERSATIONS_DIR, f"{timestamp}.json")

    def save(self, history):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

# --- Brain & Tooling ---
class AxionBrain:
    def __init__(self, config, history=None):
        self.config = config
        self.base_url = config['API']['base_url'].rstrip('/')
        self.api_key = config['API']['api_key']
        self.model = config['API']['model']
        self.temp = float(config['SETTINGS'].get('temperature', 0.7))
        
        # Time Awareness Logic
        sys_prompt = config['SETTINGS']['system_prompt']
        if config['TOOLS'].getboolean('time_awareness', fallback=True):
            current_time = datetime.now().strftime("%A, %d %B %Y, %H:%M:%S")
            sys_prompt += f"\n[System Info: Current Time is {current_time}]"

        if history:
            self.history = history
        else:
            self.history = [{"role": "system", "content": sys_prompt}]

        # Tool Registry
        self.tools_enabled = []
        self.tool_map = {}
        
        if config['TOOLS'].getboolean('web_search', fallback=True):
            try:
                self.tools_enabled.append(SearchTool.definition)
                self.tool_map['web_search'] = SearchTool.execute
            except NameError: pass

        if config['TOOLS'].getboolean('url_fetch', fallback=True):
            try:
                self.tools_enabled.append(FetchTool.definition)
                self.tool_map['fetch_url'] = FetchTool.execute
            except NameError: pass

    def chat_stream(self, user_input: str) -> Generator[str, None, None]:
        self.history.append({"role": "user", "content": user_input})
        
        while True:
            # Prepare Payload
            payload = {
                "model": self.model,
                "messages": self.history,
                "temperature": self.temp,
                "stream": True
            }
            if self.tools_enabled:
                payload["tools"] = self.tools_enabled

            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            
            try:
                response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, stream=True)
                response.raise_for_status()

                # State tracking
                accumulating_tool = False
                tool_call_data = {"id": None, "name": "", "arguments": ""}
                
                for line in response.iter_lines():
                    if not line: continue
                    decoded_line = line.decode('utf-8').strip()
                    if not decoded_line.startswith("data: "): continue
                    data_str = decoded_line[6:]
                    if data_str == "[DONE]": break
                    
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk['choices'][0]['delta']

                        # Content
                        if 'content' in delta and delta['content']:
                            yield delta['content']

                        # Tool Calls
                        if 'tool_calls' in delta:
                            t = delta['tool_calls'][0]
                            if 'id' in t:
                                accumulating_tool = True
                                tool_call_data['id'] = t['id']
                                tool_call_data['name'] = t['function']['name']
                            if 'function' in t and 'arguments' in t['function']:
                                tool_call_data['arguments'] += t['function']['arguments']

                    except json.JSONDecodeError: continue

                # Post-Stream Logic (Tool execution)
                if accumulating_tool:
                    tool_name = tool_call_data['name']
                    args_str = tool_call_data['arguments']
                    
                    # Notify User
                    yield f"\n\n> `[System] Using Tool: {tool_name}`\n"
                    
                    # Execute
                    if tool_name in self.tool_map:
                        try:
                            args = json.loads(args_str)
                            result = self.tool_map[tool_name](**args)
                        except Exception as e:
                            result = f"Error executing tool: {e}"
                    else:
                        result = f"Error: Tool {tool_name} not found locally."

                    # Update History
                    self.history.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tool_call_data['id'] or "call_default",
                            "type": "function",
                            "function": {"name": tool_name, "arguments": args_str}
                        }]
                    })
                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tool_call_data['id'] or "call_default",
                        "content": str(result)
                    })
                    # Loop back to send tool result to LLM
                    continue
                else:
                    break

            except Exception as e:
                yield f"\n[bold red]Error:[/bold red] {str(e)}"
                break

    def finalize_turn(self, full_text):
        # Only add if it wasn't a tool call turn (which is handled inside loop)
        if full_text:
            self.history.append({"role": "assistant", "content": full_text})

# --- UI Helpers ---

def print_banner(ver="1.0 Beta"):
    title = Text("AXION CLI - AI CLI Development Tool", style=f"bold {AXION_BLUE}")
    sub = Text(f"\nVer {ver} | Developed by ZNX", style=f"italic {AXION_PURPLE}")
    github = Text(f"\nGithub: https://github.com/znx-x/axion-cli", style=f"italic {USER_COLOR}")
    console.print()
    console.print(Panel(Text.assemble(title, "  ", sub, github), box=box.ROUNDED, expand=False, padding=(1, 1)))
    console.print(Text("", style="dim"))
    console.print(Text("Type 'exit' to stop the application or 'clear' to clear the screen.", style="dim"))
    console.print(Text("", style="dim"))
    console.print(Text("─" * console.width, style="dim"))
    console.print()

def render_history(history):
    """Replays the conversation history on screen."""
    for msg in history:
        role = msg.get('role')
        content = msg.get('content')
        
        # Skip system messages or empty tool calls
        if role == 'system' or not content:
            continue
            
        if role == 'user':
            console.print(f"[{USER_COLOR}]You[/{USER_COLOR}]")
            console.print(content)
            console.print()
        
        elif role == 'assistant':
            console.print(f"[{AXION_BLUE}]Axion[/{AXION_BLUE}]")
            console.print(Markdown(content))
            console.print()
            console.print(Text("─" * console.width, style="dim"))
            console.print()

# --- Main ---
def main():
    # Argument Parsing
    parser = argparse.ArgumentParser(description="Axion CLI")
    parser.add_argument("--load", type=str, help="Load conversation ID (YYYYMMDDHHMMSS)")
    args = parser.parse_args()

    config = load_config()
    
    # Init Logger & History
    logger = LogManager(args.load)
    loaded_history = logger.load()
    
    brain = AxionBrain(config, history=loaded_history)
    
    print_banner()

    # --- Render History if Loaded ---
    if args.load and loaded_history:
        console.print(f"[{USER_COLOR}]Resuming conversation: {args.load}[/{USER_COLOR}]")
        console.print(Text("─" * console.width, style="dim"))
        console.print()
        render_history(loaded_history)

    while True:
        try:
            user_input = Prompt.ask(f"[{USER_COLOR}]You[/{USER_COLOR}]")
            
            if user_input.lower() in ['exit', 'quit']:
                logger.save(brain.history) # Save on exit
                console.print(f"[{AXION_BLUE}]Saved to {logger.filename}. Goodbye.[/{AXION_BLUE}]")
                break
            
            if user_input.lower() in ['clear', 'cls']:
                console.clear()
                print_banner()
                continue
                
            if not user_input.strip(): continue

            console.print() 

            # Animation & Stream
            gen = brain.chat_stream(user_input)
            acc_text = ""
            first_chunk = None

            with console.status(f"[{AXION_PURPLE}]Axion Thinking...[/{AXION_PURPLE}]", spinner="dots2", spinner_style=AXION_BLUE):
                try:
                    first_chunk = next(gen)
                except StopIteration: pass
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    continue

            console.print(f"[{AXION_BLUE}]Axion[/{AXION_BLUE}]")
            
            with Live(Markdown(""), refresh_per_second=15, console=console) as live:
                if first_chunk:
                    acc_text += first_chunk
                    live.update(Markdown(acc_text))
                
                for chunk in gen:
                    acc_text += chunk
                    live.update(Markdown(acc_text))
            
            brain.finalize_turn(acc_text)
            logger.save(brain.history) # Auto-save after every turn

            console.print()
            console.print(Text("─" * console.width, style="dim"))
            console.print()

        except KeyboardInterrupt:
            logger.save(brain.history)
            break

if __name__ == "__main__":
    main()
