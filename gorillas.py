#!/usr/bin/env python3
"""
GORILLAS.PY - Classic QBasic Gorillas rewritten as a pure Python Curses TUI Game.

Features:
- Pure curses TUI (No external GUI/Pygame dependencies).
- Customizable Player Names, Target Score, and Gravity.
- Randomly generated procedural city skyline with illuminated windows.
- Dynamic wind indicator and physics calculations.
- Authentic Gorilla arm-raising throw animations and explosions.
- Destructible buildings / crater terrain damage.
- Sun in the sky that gets surprised when a banana passes close by.
- Supports any terminal size (80x24 or larger).
"""

import curses
import math
import random
import sys
import time


def init_colors():
    curses.start_color()
    curses.use_default_colors()

    # Define color pairs safely
    if curses.has_colors():
        curses.init_pair(1, curses.COLOR_CYAN, -1)       # Sky / Title
        curses.init_pair(2, curses.COLOR_BLUE, -1)       # Building type 1
        curses.init_pair(3, curses.COLOR_YELLOW, -1)     # Lit windows / Sun
        curses.init_pair(4, curses.COLOR_BLACK, -1)      # Dark windows
        curses.init_pair(5, curses.COLOR_GREEN, -1)      # Gorilla P1
        curses.init_pair(6, curses.COLOR_MAGENTA, -1)    # Gorilla P2
        curses.init_pair(7, curses.COLOR_YELLOW, -1)     # Banana
        curses.init_pair(8, curses.COLOR_RED, -1)        # Explosions
        curses.init_pair(9, curses.COLOR_CYAN, -1)       # Building type 2
        curses.init_pair(10, curses.COLOR_WHITE, -1)     # Text / Borders


class CitySkyline:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.skyline = [0] * width  # Building height at each x column
        self.building_colors = [0] * width
        self.grid = [[' ' for _ in range(width)] for _ in range(height)]
        self.color_grid = [[0 for _ in range(width)] for _ in range(height)]
        self.building_bounds = []  # List of (start_x, end_x, height)
        self.generate()

    def generate(self):
        min_b_width = 6
        max_b_width = 12
        min_b_height = int(self.height * 0.25)
        max_b_height = int(self.height * 0.65)

        curr_x = 2
        color_choices = [curses.COLOR_BLUE, curses.COLOR_CYAN, curses.COLOR_MAGENTA, curses.COLOR_GREEN]

        while curr_x < self.width - 4:
            b_width = random.randint(min_b_width, max_b_width)
            if curr_x + b_width >= self.width - 2:
                b_width = self.width - 2 - curr_x
            if b_width < 4:
                b_width = self.width - 2 - curr_x

            b_height = random.randint(min_b_height, max_b_height)
            color_idx = random.choice(color_choices)

            self.building_bounds.append((curr_x, curr_x + b_width - 1, b_height))

            for x in range(curr_x, curr_x + b_width):
                self.skyline[x] = b_height
                self.building_colors[x] = color_idx
                for y in range(self.height - b_height, self.height - 1):
                    # Windows pattern
                    if (y % 2 == 0) and (x % 3 == 1) and y < self.height - 2:
                        is_lit = random.random() < 0.6
                        self.grid[y][x] = '░' if is_lit else ' '
                        self.color_grid[y][x] = 3 if is_lit else color_idx
                    else:
                        self.grid[y][x] = '█'
                        self.color_grid[y][x] = color_idx

            curr_x += b_width

    def explode_impact(self, impact_x, impact_y, radius=2):
        """Destroys building blocks around impact coordinates."""
        for y in range(impact_y - radius, impact_y + radius + 1):
            for x in range(impact_x - radius, impact_x + radius + 1):
                if 0 <= x < self.width and 0 <= y < self.height - 1:
                    dist = math.hypot(x - impact_x, y - impact_y)
                    if dist <= radius:
                        self.grid[y][x] = ' '
                        self.color_grid[y][x] = 0

    def is_solid(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height - 1:
            return self.grid[y][x] != ' '
        return False


def prompt_string(stdscr, y, x, prompt_text, default_val=""):
    curses.echo()
    curses.curs_set(1)
    stdscr.addstr(y, x, f"{prompt_text} [{default_val}]: ")
    stdscr.refresh()
    inp = stdscr.getstr(y, x + len(prompt_text) + len(default_val) + 5, 20).decode('utf-8').strip()
    curses.noecho()
    curses.curs_set(0)
    return inp if inp else default_val


def prompt_float(stdscr, y, x, prompt_text, default_val):
    val_str = prompt_string(stdscr, y, x, prompt_text, str(default_val))
    try:
        return float(val_str)
    except ValueError:
        return default_val


def prompt_int(stdscr, y, x, prompt_text, default_val):
    val_str = prompt_string(stdscr, y, x, prompt_text, str(default_val))
    try:
        return int(val_str)
    except ValueError:
        return default_val


def show_title_screen(stdscr):
    stdscr.clear()
    h, w = stdscr.getmaxyx()

    title_lines = [
        "   ____   ____  ____   ___  ____    ____     _     ____  ",
        "  / ___| / __ \\|  _ \\ |_ _| |  _ \\  / ___|   / \\   / ___| ",
        " | |  _ | |  | | |_) | | |  | |_) | \\___ \\  / _ \\  \\___ \\ ",
        " | |_| || |__| |  _ <  | |  |  _ <   ___) |/ ___ \\  ___) |",
        "  \\____| \\____/|_| \\_\\|___| |_| \\_\\ |____//_/   \\_\\|____/ ",
        "                                                           ",
        "         QBasic Gorillas - Python TUI Edition              "
    ]

    start_y = max(1, (h - 20) // 2)
    for i, line in enumerate(title_lines):
        x = max(0, (w - len(line)) // 2)
        stdscr.addstr(start_y + i, x, line, curses.color_pair(1) | curses.A_BOLD)

    y_pos = start_y + len(title_lines) + 2

    p1 = prompt_string(stdscr, y_pos, max(2, (w - 40) // 2), "Name of Player 1", "Player 1")
    p2 = prompt_string(stdscr, y_pos + 2, max(2, (w - 40) // 2), "Name of Player 2", "Player 2")
    pts = prompt_int(stdscr, y_pos + 4, max(2, (w - 40) // 2), "Play to how many total points", 3)
    gravity = prompt_float(stdscr, y_pos + 6, max(2, (w - 40) // 2), "Gravity in m/s^2", 9.8)

    return p1, p2, pts, gravity


class GorillasGame:
    def __init__(self, stdscr, p1_name, p2_name, target_points, gravity):
        self.stdscr = stdscr
        self.p1_name = p1_name
        self.p2_name = p2_name
        self.target_points = target_points
        self.gravity = gravity

        self.p1_score = 0
        self.p2_score = 0
        self.current_player = 1  # 1 or 2

        self.wind = 0.0
        self.skyline = None
        self.p1_x = 0
        self.p1_y = 0
        self.p2_x = 0
        self.p2_y = 0

    def new_round(self):
        h, w = self.stdscr.getmaxyx()
        self.skyline = CitySkyline(w, h)
        # Random wind between -15.0 and +15.0
        self.wind = round(random.uniform(-15.0, 15.0), 1)

        if self.skyline.building_bounds:
            b1 = self.skyline.building_bounds[min(1, len(self.skyline.building_bounds)-1)]
            self.p1_x = (b1[0] + b1[1]) // 2
            self.p1_y = h - b1[2] - 3

        # Place Gorilla 2 on right buildings (around 75% to 90% of width)
        if self.skyline.building_bounds:
            b2_idx = max(0, len(self.skyline.building_bounds) - 2)
            b2 = self.skyline.building_bounds[b2_idx]
            self.p2_x = (b2[0] + b2[1]) // 2
            self.p2_y = h - b2[2] - 3

    def draw_gorilla(self, x, y, player_num, pose="normal"):
        color = curses.color_pair(5) if player_num == 1 else curses.color_pair(6)
        color = color | curses.A_BOLD

        if pose == "normal":
            sprite = [
                " o ",
                "/|\\",
                "/ \\"
            ]
        elif pose == "throw_left":
            sprite = [
                "\\o ",
                " |\\",
                "/ \\"
            ]
        elif pose == "throw_right":
            sprite = [
                " o/",
                "/| ",
                "/ \\"
            ]
        elif pose == "cheer":
            sprite = [
                "\\o/",
                " | ",
                "/ \\"
            ]
        elif pose == "dead":
            sprite = [
                "\\x/",
                " | ",
                "/ \\"
            ]

        for dy, line in enumerate(sprite):
            draw_y = y + dy
            draw_x = x - 1
            if 0 <= draw_y < self.skyline.height and 0 <= draw_x < self.skyline.width - 3:
                try:
                    self.stdscr.addstr(draw_y, draw_x, line, color)
                except curses.error:
                    pass

    def draw_sun(self, surprised=False):
        h, w = self.stdscr.getmaxyx()
        sun_x = w // 2
        sun_y = 2

        sun_face = "(o.o)" if surprised else "(^_^)"
        color = curses.color_pair(3) | curses.A_BOLD

        sun_art = [
            "  \\ | /  ",
            f"--{sun_face}--",
            "  / | \\  "
        ]

        for dy, line in enumerate(sun_art):
            draw_y = sun_y + dy - 1
            draw_x = sun_x - len(line) // 2
            if 0 <= draw_y < h and 0 <= draw_x < w - len(line):
                try:
                    self.stdscr.addstr(draw_y, draw_x, line, color)
                except curses.error:
                    pass

    def draw_scene(self, surprised_sun=False):
        self.stdscr.clear()
        h, w = self.stdscr.getmaxyx()

        # 1. Draw Skyline & Buildings
        for y in range(h - 1):
            for x in range(w):
                ch = self.skyline.grid[y][x]
                if ch != ' ':
                    c_idx = self.skyline.color_grid[y][x]
                    color = curses.color_pair(c_idx)
                    try:
                        self.stdscr.addch(y, x, ch, color)
                    except curses.error:
                        pass

        # 2. Draw Sun
        self.draw_sun(surprised=surprised_sun)

        # 3. Draw Gorillas
        self.draw_gorilla(self.p1_x, self.p1_y, 1, "normal")
        self.draw_gorilla(self.p2_x, self.p2_y, 2, "normal")

        # 4. Draw Header / Scoreboard
        score_str = f" {self.p1_name}: {self.p1_score}   |   {self.p2_name}: {self.p2_score} "
        try:
            self.stdscr.addstr(0, max(0, (w - len(score_str)) // 2), score_str, curses.color_pair(10) | curses.A_REVERSE)
        except curses.error:
            pass

        # 5. Draw Wind Indicator at Bottom
        wind_dir = "---->" if self.wind > 0 else ("<----" if self.wind < 0 else "0")
        wind_str = f" Wind: {wind_dir} {abs(self.wind):.1f} "
        try:
            self.stdscr.addstr(h - 1, max(0, (w - len(wind_str)) // 2), wind_str, curses.color_pair(10) | curses.A_BOLD)
        except curses.error:
            pass

        self.stdscr.refresh()

    def get_shot_parameters(self, player_num):
        h, w = self.stdscr.getmaxyx()
        player_name = self.p1_name if player_num == 1 else self.p2_name
        prompt_y = h - 2
        prompt_x = 2 if player_num == 1 else max(2, w - 40)

        # Clear prompt area
        try:
            self.stdscr.addstr(prompt_y, 0, " " * (w - 1))
        except curses.error:
            pass

        angle = prompt_float(self.stdscr, prompt_y, prompt_x, f"{player_name} Angle (0-360)", 45.0)
        velocity = prompt_float(self.stdscr, prompt_y, prompt_x, f"{player_name} Velocity (1-200)", 60.0)

        return angle, velocity

    def animate_shot(self, player_num, angle, velocity):
        h, w = self.stdscr.getmaxyx()

        # Starting position of banana
        start_x = self.p1_x if player_num == 1 else self.p2_x
        start_y = self.p1_y - 1

        # Animate throwing pose
        throw_pose = "throw_right" if player_num == 1 else "throw_left"
        self.draw_scene()
        self.draw_gorilla(start_x, self.p1_y, player_num, throw_pose)
        self.stdscr.refresh()
        time.sleep(0.2)

        # Revert gorilla back to normal
        self.draw_scene()

        # Physics Setup
        # Convert angle to radians
        # For Player 1 (facing right), 0 is right, 90 is up
        # For Player 2 (facing left), 0 is left (180 deg in standard polar), 90 is up
        if player_num == 1:
            rad = math.radians(angle)
            vx0 = velocity * math.cos(rad)
            vy0 = -velocity * math.sin(rad)  # Upward is negative Y in curses
        else:
            rad = math.radians(angle)
            vx0 = -velocity * math.cos(rad)
            vy0 = -velocity * math.sin(rad)

        t = 0.0
        dt = 0.08
        banana_chars = ["/", "-", "\\", "|"]
        b_idx = 0

        sun_x = w // 2
        sun_y = 2

        while True:
            t += dt

            # Position equation incorporating velocity, gravity, and wind
            # Wind adds horizontal acceleration component: 0.5 * wind * t^2
            curr_x = round(start_x + (vx0 * t) + (0.5 * self.wind * (t ** 2)))
            curr_y = round(start_y + (vy0 * t) + (0.5 * self.gravity * (t ** 2)))

            # Check if banana is out of bounds
            if curr_x < 0 or curr_x >= w or curr_y >= h:
                hit_target = 'out'
                break

            # Check closeness to Sun
            dist_to_sun = math.hypot(curr_x - sun_x, curr_y - sun_y)
            surprised_sun = dist_to_sun < 6

            # Redraw scene frame
            self.draw_scene(surprised_sun=surprised_sun)

            # Draw trajectory path trace or banana character
            if 0 <= curr_y < h and 0 <= curr_x < w:
                banana_char = banana_chars[b_idx % len(banana_chars)]
                b_idx += 1
                try:
                    self.stdscr.addch(curr_y, curr_x, banana_char, curses.color_pair(7) | curses.A_BOLD)
                except curses.error:
                    pass
                self.stdscr.refresh()

            # Collision Check with Gorillas
            if abs(curr_x - self.p1_x) <= 1 and abs(curr_y - (self.p1_y + 1)) <= 1:
                hit_target = 'p1'
                break
            if abs(curr_x - self.p2_x) <= 1 and abs(curr_y - (self.p2_y + 1)) <= 1:
                hit_target = 'p2'
                break

            # Collision Check with Building Terrain
            if self.skyline.is_solid(curr_x, curr_y):
                hit_target = 'building'
                break

            time.sleep(0.04)

        # Handle Collision Impact
        if hit_target in ('p1', 'p2', 'building'):
            self.animate_explosion(curr_x, curr_y, is_gorilla=(hit_target in ('p1', 'p2')))
            if hit_target == 'building':
                self.skyline.explode_impact(curr_x, curr_y, radius=2)

        return hit_target

    def animate_explosion(self, cx, cy, is_gorilla=False):
        h, w = self.stdscr.getmaxyx()
        radii = [1, 2, 3, 2, 1] if not is_gorilla else [1, 2, 3, 4, 3, 2, 1]
        exp_chars = ['*', 'O', '@', '#', '%']

        for r in radii:
            self.draw_scene()
            color = curses.color_pair(8) | curses.A_BOLD
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if math.hypot(dx, dy) <= r:
                        ex, ey = cx + dx, cy + dy
                        if 0 <= ex < w and 0 <= ey < h - 1:
                            ch = random.choice(exp_chars)
                            try:
                                self.stdscr.addch(ey, ex, ch, color)
                            except curses.error:
                                pass
            self.stdscr.refresh()
            time.sleep(0.06)

    def play(self):
        while self.p1_score < self.target_points and self.p2_score < self.target_points:
            self.new_round()

            round_over = False
            while not round_over:
                self.draw_scene()
                angle, velocity = self.get_shot_parameters(self.current_player)

                hit_result = self.animate_shot(self.current_player, angle, velocity)

                if hit_result == 'p1':
                    self.p2_score += 1
                    self.draw_scene()
                    self.draw_gorilla(self.p1_x, self.p1_y, 1, "dead")
                    self.draw_gorilla(self.p2_x, self.p2_y, 2, "cheer")
                    self.stdscr.refresh()
                    time.sleep(2.0)
                    round_over = True
                elif hit_result == 'p2':
                    self.p1_score += 1
                    self.draw_scene()
                    self.draw_gorilla(self.p1_x, self.p1_y, 1, "cheer")
                    self.draw_gorilla(self.p2_x, self.p2_y, 2, "dead")
                    self.stdscr.refresh()
                    time.sleep(2.0)
                    round_over = True
                else:
                    # Switch turn
                    self.current_player = 2 if self.current_player == 1 else 1

        # Game Winner Screen
        self.show_winner_screen()

    def show_winner_screen(self):
        self.stdscr.clear()
        h, w = self.stdscr.getmaxyx()

        winner = self.p1_name if self.p1_score >= self.target_points else self.p2_name
        winner_color = curses.color_pair(5 if self.p1_score >= self.target_points else 6) | curses.A_BOLD

        lines = [
            "🏆 GAME OVER! 🏆",
            "",
            f"   {winner} WINS THE GAME!   ",
            "",
            f"Final Score: {self.p1_name} {self.p1_score} - {self.p2_score} {self.p2_name}",
            "",
            "Press any key to exit..."
        ]

        start_y = max(1, (h - len(lines)) // 2)
        for i, line in enumerate(lines):
            x = max(0, (w - len(line)) // 2)
            attr = winner_color if "WINS" in line else (curses.color_pair(10) | curses.A_BOLD)
            try:
                self.stdscr.addstr(start_y + i, x, line, attr)
            except curses.error:
                pass

        self.stdscr.refresh()
        self.stdscr.getch()


def main(stdscr):
    init_colors()
    p1, p2, target_pts, gravity = show_title_screen(stdscr)

    game = GorillasGame(stdscr, p1, p2, target_pts, gravity)
    game.play()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        sys.exit(0)
