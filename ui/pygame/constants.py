"""Pygame UI constants — colors, sizes, layout ratios."""

# Tile size in pixels (base unit for the world map)
TILE_SIZE = 32

# World coordinate scale (must match engine/world_map.py SCALE)
WORLD_SCALE = 4

# Minimum window dimensions
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600

# Default window dimensions
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800

# Layout panel ratios (fraction of window dimensions)
MAP_PANEL_WIDTH_RATIO = 0.70
SIDE_PANEL_WIDTH_RATIO = 0.30
HEADER_HEIGHT = 56
FOOTER_HEIGHT = 72

# Event log layout
EVENT_LOG_MIN_HEIGHT = 150
EVENT_LOG_RATIO = 0.30

# HUD bar dimensions
BAR_HEIGHT = 16
BAR_INNER_HEIGHT = 12
HP_BAR_COLOR = (220, 50, 50)
HP_BAR_BG = (80, 30, 30)
XP_BAR_COLOR = (50, 180, 220)
XP_BAR_BG = (30, 50, 80)

# Terrain tile colors (RGB)
COLOR_GRASS = (76, 141, 54)
COLOR_FOREST = (34, 100, 34)
COLOR_PATH = (160, 140, 60)
COLOR_BUILDING = (140, 130, 120)
COLOR_WATER = (50, 120, 180)
COLOR_ROCK = (120, 110, 100)
COLOR_DOOR = (200, 180, 60)

# Marker colors
COLOR_PLAYER = (0, 255, 100)
COLOR_NPC = (200, 50, 200)
COLOR_ITEM = (50, 200, 200)
COLOR_VISITED = (200, 200, 50)
COLOR_UNVISITED = (200, 200, 200)

# UI panel colors
COLOR_BG = (24, 24, 32)
COLOR_PANEL_BG = (32, 32, 44)
COLOR_PANEL_BORDER = (64, 64, 80)
COLOR_TEXT = (220, 220, 220)
COLOR_TEXT_DIM = (140, 140, 140)
COLOR_TEXT_BOLD = (255, 255, 255)
COLOR_HEADER_BG = (40, 40, 56)
COLOR_ACCENT = (100, 180, 255)

# Map terrain type -> color lookup (from engine/world_map.py T_GRASS etc.)
TERRAIN_COLORS = {
    ".": COLOR_GRASS,    # T_GRASS
    "T": COLOR_FOREST,   # T_FOREST
    "=": COLOR_PATH,     # T_PATH
    "#": COLOR_BUILDING, # T_BUILDING
    "~": COLOR_WATER,    # T_WATER
    "^": COLOR_ROCK,     # T_ROCK
    "+": COLOR_DOOR,     # T_DOOR
}

# Local map terrain colors (Phase 3)
LOCAL_TERRAIN_COLORS = {
    ".": (90, 70, 50),     # floor (dark wood brown)
    "#": (60, 50, 40),     # wall (dark brown)
    "T": COLOR_FOREST,     # tree
    "=": COLOR_PATH,       # path
    "+": COLOR_DOOR,       # door / exit
    "F": (180, 60, 30),    # fireplace (orange-red)
    "T": (100, 80, 50),    # table (wood brown)
    "c": (120, 100, 60),   # chair (lighter brown)
    "K": (80, 70, 55),     # cabinet (brown)
    "S": (100, 90, 70),    # couch/shelf (tan)
    "R": (90, 80, 65),     # railing (brown-gray)
    "C": (140, 140, 140),  # counter (gray)
    "ST": (160, 160, 160), # stove (light gray)
    "SN": (100, 140, 180), # sink (blue-gray)
    "TBL": (100, 80, 50),  # table (wood brown)
    "^": COLOR_ROCK,       # rock / boulder
    "B": (80, 60, 40),     # bed (dark brown)
}
COLOR_LOCAL_FLOOR = (90, 70, 50)
COLOR_LOCAL_WALL = (60, 50, 40)
COLOR_LOCAL_PLAYER = (0, 255, 100)
COLOR_LOCAL_OBJECT = (120, 100, 70)
COLOR_LOCAL_EXIT = (200, 180, 60)

# Font sizes (base values at 1200x800 reference window)
FONT_SIZE_TITLE = 30
FONT_SIZE_BODY = 17
FONT_SIZE_SMALL = 15
FONT_SIZE_LARGE = 36

# Responsive scaling reference (baseline window size)
_SCALE_REF_W = 1200
_SCALE_REF_H = 800

# Input area
INPUT_CURSOR_BLINK_MS = 500

# Event log colors
COLOR_EVENT_PLAYER = (100, 180, 255)
COLOR_EVENT_NARRATION = (255, 255, 200)
COLOR_EVENT_SYSTEM = (140, 140, 140)
COLOR_EVENT_THINKING = (200, 200, 100)
