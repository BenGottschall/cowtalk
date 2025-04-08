import curses
import subprocess
from datetime import datetime
import threading
from queue import Queue
import textwrap
import time

class ChatUI:
    def __init__(self):
        self.screen = None
        self.input_buffer = ""
        self.cursor_x = 0
        self.message_queue = Queue()
        self.messages = []
        self.max_messages = 100  # Keep last 100 messages in history
        self.input_pad = None
        self.messages_pad = None
        self.last_height = 0
        self.last_width = 0
        self.needs_resize = False
        self.needs_message_refresh = False
        self.last_message_count = 0
        self.last_message_time = 0
        self.message_delay = 0.5  # 500ms delay between messages
        self.typing_users = {}  # Track who is typing
        self.last_input_time = 0
        self.typing_timeout = 0.5  # Reduce timeout to 500ms
        
    def start(self):
        """Initialize and start the UI"""
        self.screen = curses.initscr()
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)  # For timestamps
        curses.init_pair(2, curses.COLOR_GREEN, -1)  # For usernames
        curses.noecho()
        curses.cbreak()
        curses.curs_set(1)  # Show cursor
        self.screen.keypad(True)
        
        # Enable terminal buffering with shorter delay
        curses.halfdelay(1)  # 100ms input timeout
        
        # Initialize pads
        height, width = self.screen.getmaxyx()
        self.last_height = height
        self.last_width = width
        self._init_pads()
        
        # Draw initial screen
        self.refresh_screen(force=True)
        
        # Start message processing thread
        self.processor = threading.Thread(target=self._process_messages)
        self.processor.daemon = True
        self.processor.start()
        
    def _init_pads(self):
        """Initialize or reinitialize the pads"""
        height, width = self.screen.getmaxyx()
        # Message pad with room for lots of scrollback
        self.messages_pad = curses.newpad(1000, width)
        # Input pad for the bottom area
        self.input_pad = curses.newpad(2, width)
        
    def stop(self):
        """Clean up and restore terminal"""
        curses.nocbreak()
        self.screen.keypad(False)
        curses.echo()
        curses.endwin()
        
    def _get_cowsay(self, text):
        """Get cowsay output for text"""
        try:
            result = subprocess.run(
                ["cowsay", text],
                capture_output=True,
                text=True
            )
            return result.stdout.split('\n')
        except FileNotFoundError:
            return text.split('\n')
            
    def is_typing(self):
        """Check if the user is currently typing"""
        # Only consider typing if there are actual characters in the buffer
        return len(self.input_buffer.strip()) > 0
        
    def _get_typing_indicator(self, username):
        """Get cowsay typing indicator"""
        try:
            result = subprocess.run(
                ["cowsay", f"{username} is typing..."],
                capture_output=True,
                text=True
            )
            return result.stdout.split('\n')
        except FileNotFoundError:
            return [f"{username} is typing..."]
            
    def _process_messages(self):
        """Process messages from queue and update display"""
        while True:
            try:
                message = self.message_queue.get()
                if message is None:
                    break
                    
                if message.get("type") == "typing_status":
                    username = message.get("username")
                    is_typing = message.get("is_typing", False)
                    if is_typing:
                        self.typing_users[username] = time.time()
                    else:
                        self.typing_users.pop(username, None)
                    self.needs_message_refresh = True
                    self.refresh_screen()
                    continue
                    
                timestamp = datetime.now().strftime("%H:%M:%S")
                sender = message.get("username", "Anonymous")
                content = message.get("content", "")
                
                # Remove typing indicator if user sends a message
                self.typing_users.pop(sender, None)
                
                # Format message with timestamp
                formatted = f"{sender}: {content}"
                cowsay_lines = self._get_cowsay(formatted)
                
                # Add timestamp to first line
                cowsay_lines[0] = f"[{timestamp}] " + cowsay_lines[0]
                
                self.messages.append({
                    "timestamp": timestamp,
                    "sender": sender,
                    "content": content,
                    "lines": cowsay_lines
                })
                
                # Keep only last max_messages
                if len(self.messages) > self.max_messages:
                    self.messages.pop(0)
                    
                self.needs_message_refresh = True
                self.refresh_screen()
            except:
                pass  # Ignore any errors in message processing
            
    def add_message(self, message):
        """Add a message to the display queue"""
        self.message_queue.put(message)
        
    def get_input(self):
        """Get input from user"""
        try:
            ch = self.screen.getch()
        except curses.error:
            return None  # No input available
            
        # Check for terminal resize
        height, width = self.screen.getmaxyx()
        if height != self.last_height or width != self.last_width:
            self.last_height = height
            self.last_width = width
            self.needs_resize = True
            self._init_pads()
            self.refresh_screen(force=True)
            return None
            
        if ch == curses.KEY_BACKSPACE or ch == 127:
            if self.cursor_x > 0:
                self.input_buffer = (
                    self.input_buffer[:self.cursor_x-1] + 
                    self.input_buffer[self.cursor_x:]
                )
                self.cursor_x -= 1
                self._refresh_input()
        elif ch == curses.KEY_LEFT:
            if self.cursor_x > 0:
                self.cursor_x -= 1
                self._refresh_input()
        elif ch == curses.KEY_RIGHT:
            if self.cursor_x < len(self.input_buffer):
                self.cursor_x += 1
                self._refresh_input()
        elif ch == 10:  # Enter key
            # Check if enough time has passed since last message
            current_time = time.time()
            if current_time - self.last_message_time < self.message_delay:
                # If not enough time has passed, ignore this message
                return None
                
            message = self.input_buffer
            if message.strip():  # Only send non-empty messages
                self.last_message_time = current_time
                self.input_buffer = ""
                self.cursor_x = 0
                self._refresh_input()
                return message
            else:
                # Clear empty message without updating last_message_time
                self.input_buffer = ""
                self.cursor_x = 0
                self._refresh_input()
        elif ch >= 32 and ch < 127:  # Printable characters
            self.input_buffer = (
                self.input_buffer[:self.cursor_x] + 
                chr(ch) + 
                self.input_buffer[self.cursor_x:]
            )
            self.cursor_x += 1
            self._refresh_input()
            
        if self.needs_resize or self.needs_message_refresh:
            self.refresh_screen()
            
        return None
        
    def _refresh_input(self):
        """Refresh just the input area"""
        height, width = self.screen.getmaxyx()
        input_height = 2
        self.input_pad.erase()
        prompt = "Message: "
        try:
            # Clear the entire input line first
            self.screen.move(height - 2, 0)
            self.screen.clrtoeol()
            # Draw separator line
            self.screen.move(height - input_height - 1, 0)
            self.screen.clrtoeol()
            self.screen.addstr(height - input_height - 1, 0, "-" * (width - 1))
            # Now add our input content
            self.screen.addstr(height - 2, 0, prompt + self.input_buffer)
            # Position cursor
            self.screen.move(height - 2, len(prompt) + self.cursor_x)
            self.screen.noutrefresh()
            curses.doupdate()  # Update screen only once
        except curses.error:
            pass
            
    def refresh_screen(self, force=False):
        """Refresh the screen with current messages and input"""
        if not force and not self.needs_resize and not self.needs_message_refresh:
            return
            
        height, width = self.screen.getmaxyx()
        input_height = 2
        message_area_height = height - input_height - 1
        
        try:
            # Only redraw messages if needed
            if force or self.needs_message_refresh or len(self.messages) != self.last_message_count:
                self.messages_pad.erase()
                current_line = 0
                
                # First display typing indicators
                current_time = time.time()
                for username, last_time in list(self.typing_users.items()):
                    # Remove typing status if too old
                    if current_time - last_time > self.typing_timeout:
                        del self.typing_users[username]
                        continue
                        
                    typing_lines = self._get_typing_indicator(username)
                    lines_needed = len(typing_lines)
                    if current_line + lines_needed <= message_area_height:
                        for line in reversed(typing_lines):
                            if current_line >= message_area_height:
                                break
                            try:
                                self.messages_pad.addstr(
                                    message_area_height - 1 - current_line,
                                    0,
                                    line[:width-1]
                                )
                            except curses.error:
                                pass
                            current_line += 1
                            
                # Then display messages
                for msg in reversed(self.messages):
                    lines_needed = len(msg["lines"])
                    if current_line + lines_needed > message_area_height:
                        break
                        
                    # Display message lines
                    for line in reversed(msg["lines"]):
                        if current_line >= message_area_height:
                            break
                        try:
                            self.messages_pad.addstr(
                                message_area_height - 1 - current_line,
                                0,
                                line[:width-1]
                            )
                        except curses.error:
                            pass
                        current_line += 1
                        
                self.last_message_count = len(self.messages)
                
            # Prepare all updates without refreshing
            self.messages_pad.noutrefresh(0, 0, 0, 0, message_area_height - 1, width - 1)
            
            # Always refresh input area to keep it visible
            self._refresh_input()
            
        except curses.error:
            pass
            
        self.needs_resize = False
        self.needs_message_refresh = False 