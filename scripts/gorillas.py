#!/usr/bin/env python3
"""
gorillas.py - Classic QBasic Gorillas rewritten as a Textual TUI Game.
"""

import math
import random
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, Input, Label


class CitySkyline:
    def __init__(self, width, height):
        self.width = max(60, width)
        self.height = max(20, height)
        self.skyline = [0] * self.width
        self.grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        self.color_grid = [["blue" for _ in range(self.width)] for _ in range(self.height)]
        self.building_bounds = []
        self.generate()

    def generate(self):
        curr_x = 2
        colors = ["blue", "cyan", "magenta", "green"]

        while curr_x < self.width - 8:
            b_width = random.randint(6, 12)
            b_height = random.randint(int(self.height * 0.25), int(self.height * 0.65))
            end_x = min(curr_x + b_width, self.width - 2)
            color = random.choice(colors)

            self.building_bounds.append((curr_x, end_x, b_height))

            for x in range(curr_x, end_x):
                self.skyline[x] = b_height
                for y in range(self.height - b_height, self.height):
                    self.grid[y][x] = "█"
                    self.color_grid[y][x] = color

                # Lit windows
                for y in range(self.height - b_height + 2, self.height - 2, 2):
                    if (x - curr_x) % 2 == 1 and random.random() > 0.4:
                        self.grid[y][x] = "░"
                        self.color_grid[y][x] = "yellow"

            curr_x = end_x + 1

    def make_crater(self, cx, cy, radius=2):
        for y in range(max(0, cy - radius), min(self.height, cy + radius + 1)):
            for x in range(max(0, cx - radius), min(self.width, cx + radius + 1)):
                if math.hypot(x - cx, y - cy) <= radius:
                    self.grid[y][x] = " "
                    self.color_grid[y][x] = "black"


class GorillasCanvas(Widget):
    """Canvas widget rendering city, sun, gorillas, and throwing trajectories."""

    DEFAULT_CSS = """
    GorillasCanvas {
        width: 100%;
        height: 1fr;
        background: black;
    }
    """

    def __init__(self, p1_name="Player 1", p2_name="Player 2", target_points=3, gravity=9.8, **kwargs):
        super().__init__(**kwargs)
        self.p1_name = p1_name
        self.p2_name = p2_name
        self.target_points = target_points
        self.gravity = gravity

        self.p1_score = 0
        self.p2_score = 0
        self.current_player = 1

        self.skyline = None
        self.p1_x = 0
        self.p1_y = 0
        self.p2_x = 0
        self.p2_y = 0

        self.wind = 0.0
        self.banana_pos = None
        self.surprised_sun = False
        self.status_msg = ""
        self.p1_pose = "normal"
        self.p2_pose = "normal"

    def new_round(self):
        w = self.size.width or 80
        h = self.size.height or 24
        self.skyline = CitySkyline(w, h)
        self.wind = round(random.uniform(-15.0, 15.0), 1)

        if self.skyline.building_bounds:
            b1 = self.skyline.building_bounds[min(1, len(self.skyline.building_bounds) - 1)]
            self.p1_x = (b1[0] + b1[1]) // 2
            self.p1_y = h - b1[2] - 3

            b2_idx = max(0, len(self.skyline.building_bounds) - 2)
            b2 = self.skyline.building_bounds[b2_idx]
            self.p2_x = (b2[0] + b2[1]) // 2
            self.p2_y = h - b2[2] - 3

        self.p1_pose = "normal"
        self.p2_pose = "normal"
        self.status_msg = f"{self.p1_name if self.current_player == 1 else self.p2_name}'s turn!"
        self.refresh()

    def render(self) -> Text:
        w = self.size.width or 80
        h = self.size.height or 24

        if not self.skyline or self.skyline.width != w or self.skyline.height != h:
            self.new_round()

        out = Text()

        # Build composite grid buffer
        buf = [[" " for _ in range(w)] for _ in range(h)]
        colors = [["white" for _ in range(w)] for _ in range(h)]

        # Copy skyline grid
        for y in range(h):
            for x in range(w):
                if y < self.skyline.height and x < self.skyline.width:
                    buf[y][x] = self.skyline.grid[y][x]
                    colors[y][x] = self.skyline.color_grid[y][x]

        # Render Sun at top center
        sun_x = w // 2
        sun_face = "(o.o)" if self.surprised_sun else "(^_^)"
        if sun_x - 3 >= 0 and sun_x + 3 < w and h > 3:
            sun_str = f"\\ {sun_face} /"
            for idx, ch in enumerate(sun_str):
                if 0 <= sun_x - 3 + idx < w:
                    buf[1][sun_x - 3 + idx] = ch
                    colors[1][sun_x - 3 + idx] = "yellow"

        # Render Gorillas
        def draw_gorilla_sprite(gx, gy, player_num, pose):
            c = "green" if player_num == 1 else "magenta"
            sprite = [" o ", "/|\\", "/ \\"]
            if pose == "throw":
                sprite = [" o/", "/| ", "/ \\"]
            elif pose == "cheer":
                sprite = ["\\o/", " | ", "/ \\"]
            elif pose == "dead":
                sprite = ["\\x/", " | ", "/ \\"]

            for dy, line in enumerate(sprite):
                for dx, ch in enumerate(line):
                    py, px = gy + dy, gx - 1 + dx
                    if 0 <= py < h and 0 <= px < w:
                        buf[py][px] = ch
                        colors[py][px] = c

        draw_gorilla_sprite(self.p1_x, self.p1_y, 1, self.p1_pose)
        draw_gorilla_sprite(self.p2_x, self.p2_y, 2, self.p2_pose)

        # Render Banana projectile
        if self.banana_pos:
            bx, by = int(self.banana_pos[0]), int(self.banana_pos[1])
            if 0 <= by < h and 0 <= bx < w:
                buf[by][bx] = "🍌"
                colors[by][bx] = "yellow"

        # Construct final Rich Text output
        for y in range(h):
            for x in range(w):
                out.append(buf[y][x], style=colors[y][x])
            out.append("\n")

        return out

    def throw_banana(self, angle: float, velocity: float):
        """Perform physics trajectory calculation and animation."""
        rad = math.radians(angle)
        is_p1 = self.current_player == 1

        if is_p1:
            start_x = self.p1_x
            start_y = self.p1_y - 1
            self.p1_pose = "throw"
            vx = velocity * math.cos(rad)
            vy = -velocity * math.sin(rad)
        else:
            start_x = self.p2_x
            start_y = self.p2_y - 1
            self.p2_pose = "throw"
            vx = -velocity * math.cos(rad)
            vy = -velocity * math.sin(rad)

        x, y = float(start_x), float(start_y)
        t = 0.0
        dt = 0.15
        w = self.size.width or 80
        h = self.size.height or 24

        while True:
            t += dt
            x += (vx + self.wind) * dt
            y += vy * dt + 0.5 * self.gravity * (t**2)

            ix, iy = int(x), int(y)
            self.banana_pos = (x, y)

            # Check close to sun
            if abs(ix - w // 2) <= 4 and iy <= 3:
                self.surprised_sun = True

            self.refresh()

            # Check bounds
            if ix < 0 or ix >= w or iy >= h:
                self.status_msg = "Missed into the ocean!"
                break

            # Check hit player 1
            if abs(ix - self.p1_x) <= 1 and abs(iy - self.p1_y) <= 2:
                self.p1_pose = "dead"
                self.p2_score += 1
                self.p2_pose = "cheer"
                self.status_msg = f"HIT! {self.p2_name} scores!"
                break

            # Check hit player 2
            if abs(ix - self.p2_x) <= 1 and abs(iy - self.p2_y) <= 2:
                self.p2_pose = "dead"
                self.p1_score += 1
                self.p1_pose = "cheer"
                self.status_msg = f"HIT! {self.p1_name} scores!"
                break

            # Check hit building
            if 0 <= iy < h and 0 <= ix < w and self.skyline.grid[iy][ix] != " ":
                self.skyline.make_crater(ix, iy, 2)
                self.status_msg = "Explosion! Building hit!"
                break

        self.banana_pos = None
        self.surprised_sun = False
        self.current_player = 2 if is_p1 else 1
        self.refresh()


class GorillasScreen(Screen):
    """Gorillas game screen."""

    DEFAULT_CSS = """
    GorillasScreen {
        layout: vertical;
        background: black;
    }
    #header_bar {
        dock: top;
        height: 1;
        background: blue;
        color: yellow;
        text-align: center;
        text-style: bold;
    }
    #controls_bar {
        dock: bottom;
        height: 3;
        background: $surface;
    }
    .input_box {
        width: 15;
        margin: 0 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "exit_game", "Exit")]

    def compose(self) -> ComposeResult:
        yield Label("  QBASIC GORILLAS - TEXTUAL EDITION  ", id="header_bar")
        yield GorillasCanvas(id="canvas")
        with Horizontal(id="controls_bar"):
            yield Label(" Angle: ")
            yield Input(value="45", id="inp_angle", classes="input_box")
            yield Label(" Velocity: ")
            yield Input(value="60", id="inp_velocity", classes="input_box")
            yield Button("Throw!", variant="success", id="btn_throw")

    def on_mount(self) -> None:
        self.update_header()

    def update_header(self) -> None:
        canvas = self.query_one("#canvas", GorillasCanvas)
        wind_dir = ">>" if canvas.wind > 0 else "<<"
        text = f" {canvas.p1_name}: {canvas.p1_score} | {canvas.p2_name}: {canvas.p2_score} | Wind: {canvas.wind:.1f} {wind_dir} | {canvas.status_msg} "
        self.query_one("#header_bar", Label).update(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_throw":
            try:
                angle = float(self.query_one("#inp_angle", Input).value)
                vel = float(self.query_one("#inp_velocity", Input).value)
                canvas = self.query_one("#canvas", GorillasCanvas)
                canvas.throw_banana(angle, vel)
                self.update_header()
            except ValueError:
                pass

    def action_exit_game(self) -> None:
        self.dismiss(None)


class GorillasApp(App):
    ENABLE_COMMAND_PALETTE = False

    def on_mount(self) -> None:
        self.push_screen(GorillasScreen())


def main(stdscr=None):
    app = GorillasApp()
    app.run()


if __name__ == "__main__":
    main()
