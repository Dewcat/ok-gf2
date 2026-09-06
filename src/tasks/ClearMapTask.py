import re
from dataclasses import dataclass, field

import cv2

from ok import Box, Logger

from src.data.FeatureList import FeatureList as fL
from src.image.hsv_config import HSVRange as hR
from src.tasks.BaseGfTask import BaseGfTask, map_re


logger = Logger.get_logger(__name__)

LOCKED_TEXT = '完成前置关卡解锁'
WATCH_TEXT = '观看'
CHALLENGE_TEXT = '挑战'

MAX_EMPTY_SCANS = 3
MAX_CHAPTER_REENTRIES = 3
MAX_SEARCH_PANS = 6
MAX_OPEN_FAILURES = 2


def _center(box):
    return box.x + box.width / 2, box.y + box.height / 2


def normalize_stage_name(name):
    """Normalize harmless OCR whitespace/case differences without merging routes."""
    value = re.sub(r'\s+', '', str(name)).upper()
    return value[:-1] if value.endswith('*') else value


def _name_score(box):
    """Prefer a confident OCR result that retained the route prefix."""
    name = normalize_stage_name(box.name)
    first_digit = re.search(r'\d', name)
    prefix_length = first_digit.start() if first_digit else 0
    return prefix_length, len(name), box.confidence


@dataclass
class StageNode:
    name: str
    box: object
    aliases: set = field(default_factory=set)
    completed: bool = False

    @property
    def key(self):
        return normalize_stage_name(self.name)

    @property
    def center(self):
        return _center(self.box)


def build_stage_nodes(ocr_boxes, screen_width, screen_height):
    """Merge duplicate OCR results from the three processors into stage nodes."""
    x_threshold = screen_width * 0.065
    y_threshold = screen_height * 0.04
    groups = []

    for box in sorted(ocr_boxes, key=lambda item: (_center(item)[1], _center(item)[0])):
        bx, by = _center(box)
        best_group = None
        best_distance = None
        for group in groups:
            gx = sum(_center(item)[0] for item in group) / len(group)
            gy = sum(_center(item)[1] for item in group) / len(group)
            dx, dy = abs(bx - gx), abs(by - gy)
            if dx <= x_threshold and dy <= y_threshold:
                distance = dx / x_threshold + dy / y_threshold
                if best_distance is None or distance < best_distance:
                    best_group = group
                    best_distance = distance
        if best_group is None:
            groups.append([box])
        else:
            best_group.append(box)

    nodes = []
    for group in groups:
        representative = max(group, key=_name_score)
        aliases = {
            normalize_stage_name(box.name)
            for box in group
            if map_re.fullmatch(str(box.name))
        }
        if not aliases:
            continue
        nodes.append(StageNode(
            name=normalize_stage_name(representative.name),
            box=representative,
            aliases=aliases,
        ))
    return nodes


def associate_completion_icons(nodes, icons, screen_width, screen_height):
    """
    Attach each orange check to the nearest stage label down-left of it.

    This is deliberately separate from OCR deduplication: the check is expected
    near a card's upper-right corner, not on top of its text.
    """
    pairs = []
    expected_dx = screen_width * 0.05
    expected_dy = -screen_height * 0.06
    max_dx = screen_width * 0.16
    max_up = screen_height * 0.20
    max_down = screen_height * 0.04

    for icon_index, icon in enumerate(icons):
        ix, iy = _center(icon)
        for node_index, node in enumerate(nodes):
            nx, ny = node.center
            dx, dy = ix - nx, iy - ny
            if -screen_width * 0.01 <= dx <= max_dx and -max_up <= dy <= max_down:
                score = (
                    abs(dx - expected_dx) / max_dx
                    + abs(dy - expected_dy) / (max_up + max_down)
                )
                pairs.append((score, icon_index, node_index))

    used_icons = set()
    used_nodes = set()
    for _, icon_index, node_index in sorted(pairs):
        if icon_index in used_icons or node_index in used_nodes:
            continue
        nodes[node_index].completed = True
        used_icons.add(icon_index)
        used_nodes.add(node_index)
    return nodes


def find_orange_check_icons(frame, search_box):
    """Detect the stable orange, near-square completion badges across map skins."""
    if frame is None:
        return []

    crop = frame[
        search_box.y:search_box.y + search_box.height,
        search_box.x:search_box.x + search_box.width,
    ]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (3, 150, 170), (25, 255, 255))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    scale = min(frame.shape[1] / 1920, frame.shape[0] / 1080)
    min_side = max(10, 16 * scale)
    max_side = max(35, 55 * scale)
    min_area = max(70, 180 * scale * scale)
    icons = []

    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        aspect = width / height if height else 0
        fill_ratio = area / (width * height) if width and height else 0
        if not (min_side <= width <= max_side and min_side <= height <= max_side):
            continue
        if not (0.75 <= aspect <= 1.35 and area >= min_area and fill_ratio >= 0.45):
            continue
        icons.append(Box(
            search_box.x + x,
            search_box.y + y,
            width,
            height,
            confidence=fill_ratio,
            name=fL.now_icon,
        ))
    return icons


def infer_main_row(nodes, screen_height):
    """Infer the horizontal main road as the row nearest screen center."""
    if not nodes:
        return screen_height / 2

    tolerance = screen_height * 0.075
    rows = []
    for node in sorted(nodes, key=lambda item: item.center[1]):
        y = node.center[1]
        row = min(rows, key=lambda item: abs(item['y'] - y), default=None)
        if row is None or abs(row['y'] - y) > tolerance:
            rows.append({'y': y, 'nodes': [node]})
        else:
            row['nodes'].append(node)
            row['y'] = sum(item.center[1] for item in row['nodes']) / len(row['nodes'])

    def row_score(row):
        xs = [node.center[0] for node in row['nodes']]
        span = max(xs) - min(xs) if len(xs) > 1 else 0
        # Main roads in GF2 stay near the vertical center; branches may contain
        # as many visible nodes and may even span a few pixels farther.
        return -abs(row['y'] - screen_height / 2), len(row['nodes']), span

    return max(rows, key=row_score)['y']


def plan_stage_nodes(nodes, processed, blocked, screen_height):
    """Return unfinished branches first and the inferred main road last."""
    main_y = infer_main_row(nodes, screen_height)
    branch_distance = screen_height * 0.09
    candidates = []

    for node in nodes:
        if node.completed or node.aliases & processed or node.aliases & blocked:
            continue
        is_branch = abs(node.center[1] - main_y) > branch_distance
        candidates.append((node, is_branch))

    candidates.sort(key=lambda item: (
        0 if item[1] else 1,
        item[0].center[0],
        item[0].center[1],
    ))
    return [item[0] for item in candidates], main_y


def map_view_changed(before_nodes, after_nodes, screen_width):
    """Verify a horizontal drag from shared stage positions, tolerating OCR aliases."""
    shifts = []
    for before in before_nodes:
        for after in after_nodes:
            if before.aliases & after.aliases:
                shifts.append(abs(after.center[0] - before.center[0]))
                break

    if shifts:
        ordered = sorted(shifts)
        median_shift = ordered[len(ordered) // 2]
        return median_shift >= screen_width * 0.025

    before_names = set().union(*(node.aliases for node in before_nodes)) if before_nodes else set()
    after_names = set().union(*(node.aliases for node in after_nodes)) if after_nodes else set()
    return bool(before_names and after_names and before_names != after_names)


class ClearMapTask(BaseGfTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '推图'
        self.description = '识别完成标记，优先清理上下支路，最后推进主路'
        self.default_config.update({
            '普通OCR': True,
            '除杂色OCR1': True,
            '除杂色OCR2': True,
        })
        self.config_description.update({
            '普通OCR': '直接识别关卡名称',
            '除杂色OCR1': '过滤非纯白区域后识别关卡名称',
            '除杂色OCR2': '保留白色和浅灰区域后识别关卡名称',
        })

    def run(self):
        processors = self._ocr_processors()
        processed = set()
        blocked = set()
        open_failures = {}
        action_count = 0
        empty_scans = 0
        chapter_reentries = 0
        search_pans = 0
        pan_right = True

        while True:
            self.sleep(2)
            nodes = self._scan_nodes(processors)

            if not nodes:
                if self.ocr(match='章节进度', log=True):
                    if chapter_reentries >= MAX_CHAPTER_REENTRIES:
                        raise Exception('已退出关卡地图，但无法重新进入当前章节')
                    self._reenter_current_chapter()
                    chapter_reentries += 1
                    empty_scans = 0
                    blocked.clear()
                    search_pans = 0
                    continue

                empty_scans += 1
                if empty_scans < MAX_EMPTY_SCANS:
                    self.log_info(f'未识别到关卡，重新扫描 ({empty_scans}/{MAX_EMPTY_SCANS})')
                    continue
                if action_count:
                    self.log_info(f'推图完成，共处理 {action_count} 个关卡动作', notify=True)
                    return
                raise Exception('未找到可识别的关卡')

            empty_scans = 0
            for node in nodes:
                if node.aliases & processed:
                    node.completed = True

            candidates, main_y = plan_stage_nodes(nodes, processed, blocked, self.height)
            candidates = [
                node for node in candidates
                if open_failures.get(node.key, 0) < MAX_OPEN_FAILURES
            ]
            self._log_snapshot(nodes, candidates, main_y)

            if not candidates:
                unfinished = [
                    node for node in nodes
                    if not node.completed and not node.aliases & processed
                ]
                if search_pans < MAX_SEARCH_PANS:
                    moved = self._pan_map(
                        right=pan_right,
                        before_nodes=nodes,
                        processors=processors,
                    )
                    search_pans += 1
                    if search_pans in (2, 4):
                        pan_right = not pan_right
                    if not moved:
                        self.log_info('拖动后节点坐标未变，当前方向可能已到边界')
                    open_failures.clear()
                    continue
                if unfinished or blocked:
                    names = ', '.join(sorted(
                        {node.name for node in unfinished} | blocked
                    ))
                    raise Exception(f'可见未完成关卡均无法进入或尚未解锁: {names}')
                self.log_info(f'推图完成，共处理 {action_count} 个关卡动作', notify=True)
                return

            target = candidates[0]
            state_name, state_box = self._open_stage(target)
            if state_name is None:
                open_failures[target.key] = open_failures.get(target.key, 0) + 1
                self.log_info(
                    f'关卡 {target.name} 点击后未出现观看/挑战/锁定状态，稍后换位置重试'
                )
                self._close_details_if_open()
                continue

            open_failures.pop(target.key, None)
            search_pans = 0
            pan_right = True

            if state_name == LOCKED_TEXT:
                blocked.update(target.aliases)
                self.log_info(f'关卡 {target.name} 尚未解锁，继续寻找前置关卡')
                self.back(after_sleep=2)
                continue

            self.click(state_box, after_sleep=2)
            processed.update(target.aliases)
            action_count += 1
            chapter_reentries = 0
            blocked.clear()

            if state_name == CHALLENGE_TEXT:
                self.log_info(f'开始挑战 {target.name}')
                self.auto_battle(end_match=map_re, has_dialog=True)
            else:
                self.log_info(f'开始观看 {target.name}')
                self._finish_story(processors)

    def _ocr_processors(self):
        processors = []
        if self.config.get('普通OCR', True):
            processors.append(None)
        if self.config.get('除杂色OCR1', True):
            processors.append(self.make_hsv_isolator(hR.WHITE))
        if self.config.get('除杂色OCR2', True):
            processors.append(self.make_hsv_isolator(hR.WHITE_GRAY))
        if not processors:
            processors = [
                None,
                self.make_hsv_isolator(hR.WHITE),
                self.make_hsv_isolator(hR.WHITE_GRAY),
            ]
        return processors

    def _scan_nodes(self, processors):
        self.next_frame()
        map_box = self.box_of_screen(x=0, y=100 / 1080, to_x=1, to_y=980 / 1080)
        ocr_boxes = []
        for processor in processors:
            ocr_boxes.extend(self.ocr(
                match=map_re,
                box=map_box,
                frame_processor=processor,
            ))

        nodes = build_stage_nodes(ocr_boxes, self.width, self.height)
        icons = find_orange_check_icons(self.executor.frame, map_box)
        self.log_debug(f'地图扫描: OCR节点={len(nodes)}, 橙色勾={len(icons)}')
        return associate_completion_icons(nodes, icons, self.width, self.height)

    def _open_stage(self, node):
        self.click(node.box, after_sleep=2)
        state = self._wait_stage_state()
        if state:
            return state[0].name, state[0]

        self._close_details_if_open()
        retry_x = max(0, node.box.x - int(self.width * 80 / 1920))
        retry_box = Box(
            retry_x,
            node.box.y,
            node.box.width,
            node.box.height,
            confidence=node.box.confidence,
            name=f'retry_{node.name}',
        )
        self.click(retry_box, after_sleep=2)
        state = self._wait_stage_state()
        if state:
            return state[0].name, state[0]
        return None, None

    def _wait_stage_state(self):
        return self.wait_ocr(
            box='right',
            match=[LOCKED_TEXT, WATCH_TEXT, CHALLENGE_TEXT],
            time_out=5,
            log=True,
        )

    def _finish_story(self, processors):
        """Finish a story and recover when generic OCR misses the returned map."""
        for attempt in range(3):
            result = self.skip_dialogs(
                end_match=[map_re, '章节进度'],
                time_out=35,
                raise_if_not_found=False,
            )
            if result:
                return

            # skip_dialogs uses only the default OCR image. Recheck with the
            # same three processors used by the map scanner before waiting again.
            if self._scan_nodes(processors):
                self.log_info('通用剧情检测未命中，但地图 OCR 已确认返回')
                return
            if self.ocr(match='章节进度', log=True):
                return
            self.log_info(f'尚未确认剧情结束，继续检查 ({attempt + 1}/3)')

        raise Exception('观看剧情后长时间未返回关卡地图')

    def _close_details_if_open(self):
        if self.ocr(
                box='right',
                match=['特殊奖励', '挑战目标', '推荐等级'],
                log=True):
            self.back(after_sleep=2)

    def _pan_map(self, right, before_nodes, processors):
        direction = '右' if right else '左'
        self.log_info(f'当前视野没有可执行关卡，向{direction}搜索')
        for drag_y in (0.22, 0.38, 0.68):
            if right:
                self.swipe_relative(0.82, drag_y, 0.28, drag_y, duration=0.7, settle_time=1)
            else:
                self.swipe_relative(0.28, drag_y, 0.82, drag_y, duration=0.7, settle_time=1)
            self.sleep(1)
            after_nodes = self._scan_nodes(processors)
            if map_view_changed(before_nodes, after_nodes, self.width):
                self.log_info(f'向{direction}拖动成功，已进入新视野')
                return True
            self.log_debug(f'向{direction}拖动高度 {drag_y:.2f} 未产生节点位移')
        return False

    def _reenter_current_chapter(self):
        self.log_info('检测到已退出关卡地图，重新进入当前章节扫描遗漏支路')
        confirm = self.wait_click_ocr(
            match='确认',
            box=self.box.bottom_right,
            time_out=5,
            raise_if_not_found=False,
            after_sleep=3,
        )
        if not confirm:
            self.log_info('章节页面暂未出现确认按钮，稍后重试')

    def _log_snapshot(self, nodes, candidates, main_y):
        states = []
        candidate_keys = {node.key for node in candidates}
        for node in sorted(nodes, key=lambda item: (item.center[0], item.center[1])):
            if node.completed:
                state = '完成'
            elif node.key in candidate_keys:
                state = '候选'
            else:
                state = '跳过'
            states.append(f'{node.name}:{state}@({node.center[0]:.0f},{node.center[1]:.0f})')
        self.log_info(f'地图规划 主路Y={main_y:.0f}: ' + ', '.join(states))
