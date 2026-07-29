#!/usr/bin/env python3
"""Fullscreen solid backdrop for clean avatar-only screen recordings."""
import tkinter as tk

root = tk.Tk()
root.title("mingo-demo-backdrop")
root.configure(bg="#0a0a0c")
root.attributes("-fullscreen", True)
root.attributes("-topmost", False)
# Keep behind other demo windows
root.lower()
# Escape to quit
root.bind("<Escape>", lambda e: root.destroy())
root.mainloop()
