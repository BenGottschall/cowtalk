import curses
import subprocess
from datetime import datetime
import threading
from queue import Queue
import textwrap

class ChatUI:
    def __init__(self):
        self.screen = None
        self.input_buffer = ""
        self.cursor_x = 0
        self.message_queue = Queue()
        self.messages = []
        self.max_messages = 100  # Keep last 100 messages in history
        
    def start(self):
        """Initialize and start the UI"""
        self.screen = curses.initscr()
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)  # For timestamps
        curses.init_pair(2, curses.COLOR_GREEN, -1)  # For usernames
        curses.noecho()
        curses.cbreak()
        self.screen.keypad(True)
        self.screen.refresh()
        
        # Start message processing thread
        self.processor = threading.Thread(target=self._process_messages)
        self.processor.daemon = True
        self.processor.start()
        
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
            
    def _process_messages(self):
        """Process messages from queue and update display"""
        while True:
            message = self.message_queue.get()
            if message is None:
                break
                
            timestamp = datetime.now().strftime("%H:%M:%S")
            sender = message.get("username", "Anonymous")
            content = message.get("content", "")
            
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
                
            self.refresh_screen()
            
    def add_message(self, message):
        """Add a message to the display queue"""
        self.message_queue.put(message)
        
    def get_input(self):
        """Get input from user"""
        ch = self.screen.getch()
        if ch == curses.KEY_BACKSPACE or ch == 127:
            if self.cursor_x > 0:
                self.input_buffer = (
                    self.input_buffer[:self.cursor_x-1] + 
                    self.input_buffer[self.cursor_x:]
                )
                self.cursor_x -= 1
        elif ch == curses.KEY_LEFT:
            self.cursor_x = max(0, self.cursor_x - 1)
        elif ch == curses.KEY_RIGHT:
            self.cursor_x = min(len(self.input_buffer), self.cursor_x + 1)
        elif ch == 10:  # Enter key
            message = self.input_buffer
            self.input_buffer = ""
            self.cursor_x = 0
            return message
        elif ch >= 32 and ch < 127:  # Printable characters
            self.input_buffer = (
                self.input_buffer[:self.cursor_x] + 
                chr(ch) + 
                self.input_buffer[self.cursor_x:]
            )
            self.cursor_x += 1
        self.refresh_screen()
        return None
        
    def refresh_screen(self):
        """Refresh the screen with current messages and input"""
        height, width = self.screen.getmaxyx()
        self.screen.clear()
        
        # Calculate input area height (2 lines: prompt + input)
        input_height = 2
        
        # Draw messages area
        message_area_height = height - input_height - 1
        current_line = 0
        
        # Display messages from bottom up
        total_lines = 0
        for msg in reversed(self.messages):
            lines_needed = len(msg["lines"])
            if current_line + lines_needed > message_area_height:
                break
            
            # Display message lines
            for line in reversed(msg["lines"]):
                if current_line >= message_area_height:
                    break
                try:
                    self.screen.addstr(
                        message_area_height - 1 - current_line,
                        0,
                        line[:width-1]
                    )
                except curses.error:
                    pass
                current_line += 1
                
        # Draw separator
        try:
            self.screen.addstr(height - input_height - 1, 0, "-" * (width - 1))
        except curses.error:
            pass
            
        # Draw input area
        prompt = "Message: "
        try:
            self.screen.addstr(height - 2, 0, prompt)
            self.screen.addstr(height - 2, len(prompt), self.input_buffer)
        except curses.error:
            pass
            
        # Position cursor
        try:
            self.screen.move(height - 2, len(prompt) + self.cursor_x)
        except curses.error:
            pass
            
        self.screen.refresh() 