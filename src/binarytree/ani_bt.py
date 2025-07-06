from manim import *

class BinarySearchTextStyle(Scene):
    def construct(self):
        status = Text("Binary Search: Find 13", font_size=28).to_edge(UP, buff=0.3)
        self.play(Write(status))

        def format_code_vgroup(code_lines, font_size=17, scale=0.9, h_buff=1.0, v_buff=0.1):
            code_text = VGroup()
            for line in code_lines:
                text = Text(line, font="monospace", font_size=font_size).scale(scale)
                code_text.add(text)
            code_text.arrange(DOWN, aligned_edge=LEFT, buff=v_buff)
            return code_text.to_edge(LEFT, buff=h_buff)

        code_lines = [
            "def binary_search(arr,target):",
            "    left , right =0,len(arr)-1",
            "    while left <= right:",
            "        mid =(left + right)//2",
            "        if arr[mid]==target:",
            "            return mid",
            "        elif arr[mid]<target:",
            "            left =mid + 1",
            "        else:",
            "            right =mid - 1",
            "    return -1"
        ]
        code_group = format_code_vgroup(code_lines)
        self.play(FadeIn(code_group))

        pointer = Triangle(color=YELLOW).scale(0.12).rotate(-PI / 2)
        pointer.next_to(code_group[0], LEFT, buff=0.15)
        self.add(pointer)

        def move_pointer(index):
            return pointer.animate(run_time=0.5).next_to(code_group[index], LEFT, buff=0.15)

        array_vals = [2, 5, 8, 10, 13, 15, 18, 20]
        square_size = 0.6
        boxes = [Square(square_size).set_stroke(WHITE) for _ in array_vals]
        texts = [Text(str(val), font="monospace", font_size=18).move_to(boxes[i]) for i, val in enumerate(array_vals)]
        array = VGroup(*[VGroup(boxes[i], texts[i]) for i in range(len(array_vals))]).arrange(RIGHT, buff=0.1)
        array.next_to(code_group, RIGHT, buff=0.7).align_to(code_group, ORIGIN)
        self.play(FadeIn(array))

        def pointer_arrow(label, color, direction=UP):
            arrow = Arrow(direction, -direction, buff=0.05, color=color).scale(0.22)
            tag = Text(label, font_size=14, color=color).next_to(arrow, direction, buff=0.05)
            return VGroup(arrow, tag)

        low_arrow = pointer_arrow("low", BLUE, direction=DOWN)
        high_arrow = pointer_arrow("high", RED, direction=DOWN)
        mid_arrow = pointer_arrow("mid", YELLOW, direction=UP)

        low_arrow.next_to(array[0], DOWN, buff=0.8).shift(LEFT * 0.15)
        high_arrow.next_to(array[7], DOWN, buff=0.8).shift(RIGHT * 0.15)
        self.play(FadeIn(low_arrow, high_arrow), run_time=0.5)

        def move_arrows(low, mid, high, show_mid=False):
            low_pos = array[low]
            high_pos = array[high]
            mid_pos = array[mid]
            low_shift = LEFT * 0.15
            high_shift = RIGHT * 0.15
            mid_anim = []
            if show_mid:
                mid_arrow.next_to(mid_pos, UP, buff=0.1)
                if mid_arrow not in self.mobjects:
                    self.add(mid_arrow)
                mid_anim = [mid_arrow.animate(run_time=1.0).next_to(mid_pos, UP, buff=0.1)]
            return AnimationGroup(
                low_arrow.animate(run_time=1.0).next_to(low_pos, DOWN, buff=0.1).shift(low_shift),
                high_arrow.animate(run_time=1.0).next_to(high_pos, DOWN, buff=0.1).shift(high_shift),
                *mid_anim,
                lag_ratio=0.1
            )

        steps = [
            {"line": 1, "desc": "Initialize: left=0, right=7", "low": 0, "mid": 3, "high": 7},
            {"line": 3, "desc": "mid = (0 + 7) // 2 = 3", "show_mid": True},
            {"line": 7, "desc": "arr[3] = 10 < 13 → left = 4", "low": 4, "mid": 3, "high": 7},
            {"line": 3, "desc": "mid = (4 + 7) // 2 = 5", "low": 4, "mid": 5, "high": 7, "show_mid": True},
            {"line": 7, "desc": "arr[5] = 15 > 13 → right = 4", "low": 4, "mid": 4, "high": 4},
            {"line": 4, "desc": "arr[4] = 13 → Target found!"},
        ]

        for step in steps:
            self.play(move_pointer(step["line"]), run_time=0.5)
            self.play(Transform(status, Text(step["desc"], font_size=28).to_edge(UP, buff=0.3)), run_time=0.5)
            if "low" in step or "mid" in step or "high" in step:
                self.play(move_arrows(
                    step.get("low", 0),
                    step.get("mid", 0),
                    step.get("high", 0),
                    show_mid=step.get("show_mid", False)
                ))
            self.wait(1.3)

        self.play(FadeOut(code_group, pointer, array, low_arrow, mid_arrow, high_arrow, status))
