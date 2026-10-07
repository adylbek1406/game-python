"""Star Dodger — 2D space shooter on pygame."""

import array
import json
import math
import random
import sys
from datetime import datetime
from pathlib import Path

import pygame

# --- constants ---
WIDTH, HEIGHT = 800, 600
FPS = 60
PLAYER_SPEED = 5
BULLET_SPEED = 10
BASE_SPAWN_INTERVAL_MS = 900
SCORE_PER_LEVEL = 100
POWERUP_DROP_CHANCE = 0.18
POWERUP_DURATION_MS = 6000
HIT_INVULN_MS = 1200
BOSS_ALERT_MS = 2000
HIGHSCORE_FILE = Path(__file__).parent / "highscores.json"
MAX_HIGHSCORES = 10
NAME_MAX_LEN = 10

# colors
BG = (10, 12, 28)
STAR_COLOR = (180, 190, 220)
PLAYER_COLOR = (80, 200, 255)
BULLET_COLOR = (255, 230, 80)
ENEMY_COLORS = [(255, 90, 90), (255, 140, 60), (200, 80, 200)]
BOSS_COLOR = (255, 60, 120)
TEXT_COLOR = (230, 235, 255)
ACCENT = (100, 255, 180)

DIFFICULTY = {
    "easy": {"speed_mul": 0.75, "spawn_mul": 1.3, "max_enemies": 8, "label": "Easy"},
    "normal": {
        "speed_mul": 1.0,
        "spawn_mul": 1.0,
        "max_enemies": 12,
        "label": "Normal",
    },
    "hard": {"speed_mul": 1.35, "spawn_mul": 0.7, "max_enemies": 18, "label": "Hard"},
}

POWERUP_HEALTH = "health"
POWERUP_RAPID = "rapid"
POWERUP_SHIELD = "shield"
POWERUP_COLORS = {
    POWERUP_HEALTH: (80, 255, 120),
    POWERUP_RAPID: (255, 220, 60),
    POWERUP_SHIELD: (80, 160, 255),
}

MUSIC_NOTES = {
    "C3": 130.81,
    "E3": 164.81,
    "G3": 196.0,
    "A3": 220.0,
    "C4": 261.63,
    "D4": 293.66,
    "E4": 329.63,
    "G4": 392.0,
    "A4": 440.0,
    "B4": 493.88,
}


def make_stars(count: int) -> list[tuple[int, int, int]]:
    return [
        (random.randint(0, WIDTH), random.randint(0, HEIGHT), random.randint(1, 3))
        for _ in range(count)
    ]


def make_tone(
    frequency: float, duration_ms: int, volume: float = 0.35
) -> pygame.mixer.Sound | None:
    try:
        rate = 22050
        n = max(1, int(rate * duration_ms / 1000))
        samples = array.array("h", [0] * n * 2)
        for i in range(n):
            wave = int(32767 * volume * math.sin(2 * math.pi * frequency * i / rate))
            samples[i * 2] = wave
            samples[i * 2 + 1] = wave
        return pygame.mixer.Sound(buffer=samples)
    except pygame.error:
        return None


def make_music_loop(
    pattern: list[tuple[str, float]], bpm: int = 110, volume: float = 0.18
) -> pygame.mixer.Sound | None:
    try:
        rate = 22050
        beat = 60 / bpm
        samples = array.array("h")
        for note, beats in pattern:
            n = max(1, int(rate * beat * beats))
            freq = MUSIC_NOTES.get(note, 220.0)
            for i in range(n):
                t = i / rate
                env = min(1.0, i / (n * 0.1), (n - i) / (n * 0.2))
                wave = int(32767 * volume * env * math.sin(2 * math.pi * freq * t))
                samples.append(wave)
                samples.append(wave)
        return pygame.mixer.Sound(buffer=samples)
    except pygame.error:
        return None


BGM_PATTERN = [
    ("C3", 1),
    ("E3", 1),
    ("G3", 1),
    ("C4", 1),
    ("A3", 1),
    ("G3", 1),
    ("E3", 1),
    ("C3", 1),
    ("G3", 0.5),
    ("E3", 0.5),
    ("C4", 1),
    ("G4", 1),
    ("E4", 1),
    ("D4", 1),
    ("C4", 2),
]

BOSS_BGM_PATTERN = [
    ("A3", 0.5),
    ("C4", 0.5),
    ("E4", 0.5),
    ("A4", 0.5),
    ("G4", 0.5),
    ("E4", 0.5),
    ("C4", 0.5),
    ("A3", 0.5),
    ("E4", 1),
    ("G4", 1),
    ("A4", 1),
    ("B4", 1),
    ("A4", 0.5),
    ("G4", 0.5),
    ("E4", 0.5),
    ("C4", 0.5),
]


class Sounds:
    def __init__(self):
        self.enabled = True
        self.music_channel = None
        self.shoot = make_tone(880, 60, 0.2)
        self.hit = make_tone(220, 120, 0.35)
        self.explosion = make_tone(110, 200, 0.4)
        self.powerup = make_tone(660, 150, 0.3)
        self.hurt = make_tone(150, 250, 0.45)
        self.level_up = make_tone(523, 80, 0.3)
        self.boss_alert = make_tone(330, 400, 0.4)
        self.boss_hit = make_tone(180, 90, 0.35)
        self.bgm = make_music_loop(BGM_PATTERN, bpm=108)
        self.boss_bgm = make_music_loop(BOSS_BGM_PATTERN, bpm=138, volume=0.22)

    def play(self, sound: pygame.mixer.Sound | None):
        if self.enabled and sound:
            sound.play()

    def play_music(self, boss: bool = False):
        if not self.enabled:
            return
        track = self.boss_bgm if boss else self.bgm
        if not track:
            return
        if self.music_channel:
            self.music_channel.stop()
        self.music_channel = track.play(loops=-1)

    def stop_music(self):
        if self.music_channel:
            self.music_channel.stop()
            self.music_channel = None


def load_highscores() -> list[dict]:
    if not HIGHSCORE_FILE.exists():
        return []
    try:
        data = json.loads(HIGHSCORE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_highscores(scores: list[dict]):
    try:
        HIGHSCORE_FILE.write_text(
            json.dumps(scores[:MAX_HIGHSCORES], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def qualifies_for_highscore(score: int, scores: list[dict]) -> bool:
    if len(scores) < MAX_HIGHSCORES:
        return True
    return score > min(s["score"] for s in scores)


def add_highscore(
    scores: list[dict], name: str, score: int, level: int, difficulty: str
) -> list[dict]:
    entry = {
        "name": name[:NAME_MAX_LEN] or "Pilot",
        "score": score,
        "level": level,
        "difficulty": difficulty,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    scores.append(entry)
    scores.sort(key=lambda x: x["score"], reverse=True)
    save_highscores(scores)
    return scores[:MAX_HIGHSCORES]


class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.base_image = pygame.Surface((40, 32), pygame.SRCALPHA)
        pts = [(20, 0), (38, 28), (20, 22), (2, 28)]
        pygame.draw.polygon(self.base_image, PLAYER_COLOR, pts)
        pygame.draw.polygon(self.base_image, (200, 240, 255), pts, 2)
        self.image = self.base_image.copy()
        self.rect = self.image.get_rect(center=(WIDTH // 2, HEIGHT - 60))
        self.cooldown = 0
        self.rapid_timer = 0
        self.shield_timer = 0
        self.invuln_timer = 0
        self.blink = 0

    @property
    def fire_cooldown(self) -> int:
        return 6 if self.rapid_timer > 0 else 12

    @property
    def invulnerable(self) -> bool:
        return self.shield_timer > 0 or self.invuln_timer > 0

    @property
    def shielded(self) -> bool:
        return self.shield_timer > 0

    def apply_powerup(self, kind: str):
        if kind == POWERUP_HEALTH:
            return POWERUP_HEALTH
        if kind == POWERUP_RAPID:
            self.rapid_timer = POWERUP_DURATION_MS
            return POWERUP_RAPID
        if kind == POWERUP_SHIELD:
            self.shield_timer = POWERUP_DURATION_MS
            return POWERUP_SHIELD
        return None

    def take_hit(self):
        self.invuln_timer = HIT_INVULN_MS

    def update(self, keys: pygame.key.ScancodeWrapper, dt: int):
        dx = dy = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx = -PLAYER_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx = PLAYER_SPEED
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy = -PLAYER_SPEED
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy = PLAYER_SPEED

        self.rect.x = max(0, min(WIDTH - self.rect.width, self.rect.x + dx))
        self.rect.y = max(HEIGHT // 2, min(HEIGHT - self.rect.height, self.rect.y + dy))

        if self.cooldown > 0:
            self.cooldown -= 1
        if self.rapid_timer > 0:
            self.rapid_timer = max(0, self.rapid_timer - dt)
        if self.shield_timer > 0:
            self.shield_timer = max(0, self.shield_timer - dt)
        if self.invuln_timer > 0:
            self.invuln_timer = max(0, self.invuln_timer - dt)

        self.blink += 1
        self.image = self.base_image.copy()
        if self.shielded:
            pygame.draw.circle(
                self.image, (80, 180, 255), self.image.get_rect().center, 26, 3
            )
        if self.invuln_timer > 0 and self.blink % 8 < 4:
            self.image.set_alpha(100)
        else:
            self.image.set_alpha(255)

    def shoot(self) -> list["Bullet"]:
        if self.cooldown > 0:
            return []
        self.cooldown = self.fire_cooldown
        cx, top = self.rect.centerx, self.rect.top
        if self.rapid_timer > 0:
            return [Bullet(cx - 8, top), Bullet(cx + 8, top)]
        return [Bullet(cx, top)]


class Bullet(pygame.sprite.Sprite):
    def __init__(self, x: int, y: int):
        super().__init__()
        self.image = pygame.Surface((6, 14), pygame.SRCALPHA)
        pygame.draw.rect(self.image, BULLET_COLOR, (0, 0, 6, 14), border_radius=2)
        self.rect = self.image.get_rect(center=(x, y))

    def update(self):
        self.rect.y -= BULLET_SPEED
        if self.rect.bottom < 0:
            self.kill()


class BossBullet(pygame.sprite.Sprite):
    def __init__(self, x: int, y: int, speed: float):
        super().__init__()
        self.image = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.circle(self.image, (255, 80, 80), (5, 5), 5)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = speed

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > HEIGHT:
            self.kill()


class Enemy(pygame.sprite.Sprite):
    def __init__(self, level: int, diff: dict):
        super().__init__()
        self.size = random.randint(28, 48)
        self.base_image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        self.color = random.choice(ENEMY_COLORS)
        pygame.draw.ellipse(self.base_image, self.color, self.base_image.get_rect())
        pygame.draw.ellipse(
            self.base_image, (255, 255, 255), self.base_image.get_rect(), 2
        )
        self.image = self.base_image.copy()
        self.rect = self.image.get_rect(
            midtop=(random.randint(self.size, WIDTH - self.size), -self.size)
        )
        base_min, base_max = 2, 5
        scale = diff["speed_mul"] * (1 + level * 0.08)
        self.speed = random.uniform(base_min, base_max) * scale
        self.rot = random.uniform(0, 360)
        self.rot_speed = random.uniform(-3, 3)

    def update(self):
        self.rect.y += self.speed
        self.rot = (self.rot + self.rot_speed) % 360
        self.image = pygame.transform.rotate(self.base_image, self.rot)
        self.rect = self.image.get_rect(center=self.rect.center)
        if self.rect.top > HEIGHT:
            self.kill()


class Boss(pygame.sprite.Sprite):
    def __init__(self, level: int, diff: dict):
        super().__init__()
        self.level = level
        self.max_hp = 25 + level * 12
        self.hp = self.max_hp
        w, h = 120, 80
        self.base_image = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(
            self.base_image,
            BOSS_COLOR,
            [
                (w // 2, 0),
                (w - 8, h // 2),
                (w // 2 + 20, h),
                (w // 2 - 20, h),
                (8, h // 2),
            ],
        )
        pygame.draw.polygon(
            self.base_image,
            (255, 180, 200),
            [
                (w // 2, 0),
                (w - 8, h // 2),
                (w // 2 + 20, h),
                (w // 2 - 20, h),
                (8, h // 2),
            ],
            3,
        )
        pygame.draw.circle(self.base_image, (255, 60, 80), (w // 2 - 22, h // 2 - 8), 8)
        pygame.draw.circle(self.base_image, (255, 60, 80), (w // 2 + 22, h // 2 - 8), 8)
        self.image = self.base_image.copy()
        self.rect = self.image.get_rect(midtop=(WIDTH // 2, -h))
        self.target_y = 80
        self.phase = 0.0
        self.shoot_timer = 0
        self.entering = True
        self.speed_x = 2.2 * diff["speed_mul"] * (1 + level * 0.05)

    def update(self, dt: int, boss_bullets: pygame.sprite.Group):
        if self.entering:
            self.rect.y += 2
            if self.rect.top >= self.target_y:
                self.entering = False
        else:
            self.phase += 0.03
            self.rect.centerx = int(WIDTH // 2 + math.sin(self.phase) * 260)
            self.rect.x = max(10, min(WIDTH - self.rect.width - 10, self.rect.x))

        self.shoot_timer += dt
        interval = max(500, 1400 - self.level * 60)
        if not self.entering and self.shoot_timer >= interval:
            self.shoot_timer = 0
            cx = self.rect.centerx
            cy = self.rect.bottom - 8
            spread = [-30, 0, 30]
            speed = 4 + self.level * 0.3
            for offset in spread:
                boss_bullets.add(BossBullet(cx + offset, cy, speed))

    def take_damage(self, amount: int = 1) -> bool:
        self.hp -= amount
        return self.hp <= 0

    @property
    def hp_ratio(self) -> float:
        return max(0, self.hp / self.max_hp)


class PowerUp(pygame.sprite.Sprite):
    def __init__(self, x: int, y: int, kind: str):
        super().__init__()
        self.kind = kind
        self.image = pygame.Surface((28, 28), pygame.SRCALPHA)
        color = POWERUP_COLORS[kind]
        pygame.draw.circle(self.image, color, (14, 14), 12)
        pygame.draw.circle(self.image, (255, 255, 255), (14, 14), 12, 2)
        if kind == POWERUP_HEALTH:
            pygame.draw.rect(self.image, (255, 255, 255), (12, 6, 4, 16))
            pygame.draw.rect(self.image, (255, 255, 255), (6, 12, 16, 4))
        elif kind == POWERUP_RAPID:
            pygame.draw.polygon(
                self.image, (255, 255, 255), [(14, 5), (20, 18), (8, 18)]
            )
        else:
            pygame.draw.circle(self.image, (255, 255, 255), (14, 14), 6, 2)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = 2

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > HEIGHT:
            self.kill()


class Particle(pygame.sprite.Sprite):
    def __init__(self, x: int, y: int, color: tuple[int, int, int]):
        super().__init__()
        self.image = pygame.Surface((6, 6), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (3, 3), 3)
        self.rect = self.image.get_rect(center=(x, y))
        angle = random.uniform(0, math.tau)
        speed = random.uniform(2, 6)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 30

    def update(self):
        self.rect.x += int(self.vx)
        self.rect.y += int(self.vy)
        self.life -= 1
        if self.life <= 0:
            self.kill()


def draw_stars(surface: pygame.Surface, stars: list, offset: float):
    for x, y, r in stars:
        y_pos = (y + offset) % HEIGHT
        pygame.draw.circle(surface, STAR_COLOR, (x, int(y_pos)), r)


def spawn_particles(
    group: pygame.sprite.Group, x: int, y: int, color: tuple[int, int, int], n: int = 10
):
    for _ in range(n):
        group.add(Particle(x, y, color))


def draw_text(surface, font, text, pos, color=TEXT_COLOR, center=False):
    rendered = font.render(text, True, color)
    rect = rendered.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    surface.blit(rendered, rect)


def draw_boss_bar(screen, font, boss: Boss):
    bar_w, bar_h = 400, 18
    x = (WIDTH - bar_w) // 2
    y = 16
    pygame.draw.rect(screen, (40, 40, 60), (x, y, bar_w, bar_h), border_radius=4)
    fill = int(bar_w * boss.hp_ratio)
    if fill > 0:
        pygame.draw.rect(screen, BOSS_COLOR, (x, y, fill, bar_h), border_radius=4)
    pygame.draw.rect(screen, (200, 200, 220), (x, y, bar_w, bar_h), 2, border_radius=4)
    draw_text(
        screen,
        font,
        f"BOSS  Lv.{boss.level}",
        (WIDTH // 2, y + bar_h + 14),
        (255, 150, 170),
        center=True,
    )


def get_level(score: int) -> int:
    return score // SCORE_PER_LEVEL + 1


def spawn_interval(level: int, diff: dict) -> int:
    base = BASE_SPAWN_INTERVAL_MS * diff["spawn_mul"]
    return max(350, int(base - level * 45))


def max_enemies(level: int, diff: dict) -> int:
    return min(diff["max_enemies"] + level // 2, 25)


def maybe_drop_powerup(powerups: pygame.sprite.Group, x: int, y: int):
    if random.random() < POWERUP_DROP_CHANCE:
        kind = random.choice([POWERUP_HEALTH, POWERUP_RAPID, POWERUP_SHIELD])
        powerups.add(PowerUp(x, y, kind))


def init_state(diff_key: str) -> dict:
    player = Player()
    return {
        "player": player,
        "bullets": pygame.sprite.Group(),
        "enemies": pygame.sprite.Group(),
        "particles": pygame.sprite.Group(),
        "powerups": pygame.sprite.Group(),
        "boss_bullets": pygame.sprite.Group(),
        "all_sprites": pygame.sprite.Group(player),
        "boss": None,
        "boss_active": False,
        "boss_alert_timer": 0,
        "pending_boss_level": None,
        "score": 0,
        "lives": 3,
        "spawn_timer": 0,
        "level": 1,
        "difficulty": diff_key,
        "game_over": False,
        "paused": False,
        "entering_name": False,
        "player_name": "",
        "name_saved": False,
    }


def start_boss_fight(state: dict, level: int, diff: dict, sounds: Sounds):
    state["enemies"].empty()
    state["boss_bullets"].empty()
    state["boss"] = Boss(level, diff)
    state["boss_active"] = True
    state["boss_alert_timer"] = BOSS_ALERT_MS
    state["pending_boss_level"] = level
    sounds.play(sounds.boss_alert)
    sounds.play_music(boss=True)


def finish_boss_fight(state: dict, sounds: Sounds):
    level = state["pending_boss_level"] or state["level"]
    state["score"] += 50 + level * 20
    state["level"] = level
    state["boss"] = None
    state["boss_active"] = False
    state["boss_alert_timer"] = 0
    state["pending_boss_level"] = None
    state["boss_bullets"].empty()
    sounds.play(sounds.level_up)
    sounds.play_music(boss=False)


def player_hit(state: dict, sounds: Sounds):
    player: Player = state["player"]
    spawn_particles(
        state["particles"],
        player.rect.centerx,
        player.rect.centery,
        (255, 100, 100),
        16,
    )
    sounds.play(sounds.hurt)
    state["lives"] -= 1
    player.take_hit()
    if state["lives"] <= 0:
        sounds.play(sounds.explosion)
        state["game_over"] = True


def draw_hud(screen, font, state: dict):
    diff = DIFFICULTY[state["difficulty"]]
    draw_text(screen, font, f"Score: {state['score']}", (16, 12))
    draw_text(screen, font, f"Lives: {state['lives']}", (16, 40), ACCENT)
    if not state["boss_active"]:
        draw_text(screen, font, f"Level: {state['level']}", (16, 68), (255, 200, 100))
    draw_text(screen, font, diff["label"], (WIDTH - 110, 12), (150, 160, 190))

    player: Player = state["player"]
    y = 96
    if player.rapid_timer > 0:
        draw_text(
            screen,
            font,
            f"Rapid: {player.rapid_timer // 1000 + 1}s",
            (16, y),
            POWERUP_COLORS[POWERUP_RAPID],
        )
        y += 28
    if player.shield_timer > 0:
        draw_text(
            screen,
            font,
            f"Shield: {player.shield_timer // 1000 + 1}s",
            (16, y),
            POWERUP_COLORS[POWERUP_SHIELD],
        )

    if state["boss_active"] and state["boss"]:
        draw_boss_bar(screen, font, state["boss"])
    if state["boss_alert_timer"] > 0:
        draw_text(
            screen,
            font,
            "BOSS INCOMING!",
            (WIDTH // 2, HEIGHT // 2 - 20),
            (255, 100, 120),
            center=True,
        )


def draw_highscores(screen, big_font, font, scores: list[dict]):
    screen.fill(BG)
    draw_text(screen, big_font, "HIGH SCORES", (WIDTH // 2, 50), ACCENT, center=True)
    if not scores:
        draw_text(
            screen,
            font,
            "No records yet — be the first!",
            (WIDTH // 2, 200),
            center=True,
        )
    else:
        draw_text(
            screen,
            font,
            f"{'#':<3} {'Name':<12} {'Score':>6}  {'Lvl':>3}  {'Diff':<6}  Date",
            (80, 110),
            (140, 150, 180),
        )
        for i, entry in enumerate(scores[:MAX_HIGHSCORES], 1):
            line = (
                f"{i:<3} {entry['name']:<12} {entry['score']:>6}  "
                f"{entry.get('level', '-'):>3}  {entry.get('difficulty', '-'):<6}  {entry.get('date', '')}"
            )
            color = ACCENT if i == 1 else TEXT_COLOR
            draw_text(screen, font, line, (80, 110 + i * 30), color)
    draw_text(
        screen,
        font,
        "Press Esc or H to return",
        (WIDTH // 2, HEIGHT - 50),
        (140, 150, 180),
        center=True,
    )


def draw_menu(screen, big_font, font, scores: list[dict]):
    screen.fill(BG)
    draw_text(screen, big_font, "STAR DODGER", (WIDTH // 2, 90), ACCENT, center=True)
    draw_text(screen, font, "Choose difficulty:", (WIDTH // 2, 175), center=True)
    draw_text(
        screen,
        font,
        "1 — Easy     2 — Normal     3 — Hard",
        (WIDTH // 2, 215),
        center=True,
    )
    draw_text(
        screen, font, "H — High scores", (WIDTH // 2, 265), (140, 150, 180), center=True
    )
    draw_text(
        screen,
        font,
        "WASD — move   Space — shoot   Boss every level!",
        (WIDTH // 2, 330),
        (140, 150, 180),
        center=True,
    )
    draw_text(
        screen,
        font,
        "P — pause   M — mute   Esc — quit",
        (WIDTH // 2, 365),
        (140, 150, 180),
        center=True,
    )

    draw_text(
        screen, font, "Top scores:", (WIDTH // 2, 420), (255, 200, 100), center=True
    )
    if scores:
        for i, entry in enumerate(scores[:3], 1):
            draw_text(
                screen,
                font,
                f"{i}. {entry['name']} — {entry['score']} ({entry.get('difficulty', '?')})",
                (WIDTH // 2, 450 + i * 28),
                TEXT_COLOR if i > 1 else ACCENT,
                center=True,
            )
    else:
        draw_text(
            screen,
            font,
            "No records yet",
            (WIDTH // 2, 478),
            (120, 130, 160),
            center=True,
        )


def handle_name_input(
    state: dict, event: pygame.event.Event, highscores: list[dict]
) -> list[dict]:
    if event.key == pygame.K_RETURN and state["player_name"].strip():
        highscores = add_highscore(
            highscores,
            state["player_name"].strip(),
            state["score"],
            state["level"],
            state["difficulty"],
        )
        state["entering_name"] = False
        state["name_saved"] = True
    elif event.key == pygame.K_BACKSPACE:
        state["player_name"] = state["player_name"][:-1]
    elif event.unicode.isalnum() or event.unicode in "-_":
        if len(state["player_name"]) < NAME_MAX_LEN:
            state["player_name"] += event.unicode
    return highscores


def run_game(
    screen,
    clock,
    font,
    big_font,
    stars,
    sounds: Sounds,
    diff_key: str,
    highscores: list[dict],
):
    state = init_state(diff_key)
    star_offset = 0.0
    diff = DIFFICULTY[diff_key]
    sounds.play_music(boss=False)

    running = True
    while running:
        dt = clock.tick(FPS)
        star_offset = (star_offset + 0.4) % HEIGHT
        player: Player = state["player"]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sounds.stop_music()
                return "quit", highscores
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if state["entering_name"]:
                        state["entering_name"] = False
                        state["name_saved"] = True
                    else:
                        sounds.stop_music()
                        return "menu", highscores
                if state["entering_name"]:
                    highscores = handle_name_input(state, event, highscores)
                    continue
                if event.key == pygame.K_m:
                    sounds.enabled = not sounds.enabled
                    if sounds.enabled:
                        sounds.play_music(boss=state["boss_active"])
                    else:
                        sounds.stop_music()
                if event.key == pygame.K_p and not state["game_over"]:
                    state["paused"] = not state["paused"]
                if (
                    event.key == pygame.K_r
                    and state["game_over"]
                    and not state["entering_name"]
                ):
                    state = init_state(diff_key)
                    player = state["player"]
                    sounds.play_music(boss=False)
                if (
                    event.key == pygame.K_SPACE
                    and not state["game_over"]
                    and not state["paused"]
                ):
                    new_bullets = player.shoot()
                    if new_bullets:
                        state["bullets"].add(new_bullets)
                        sounds.play(sounds.shoot)

        keys = pygame.key.get_pressed()
        if (
            not state["game_over"]
            and not state["paused"]
            and not state["entering_name"]
        ):
            player.update(keys, dt)
            if keys[pygame.K_SPACE] and player.cooldown == 0:
                new_bullets = player.shoot()
                if new_bullets:
                    state["bullets"].add(new_bullets)
                    sounds.play(sounds.shoot)

            state["bullets"].update()
            state["particles"].update()
            state["powerups"].update()

            if state["boss_alert_timer"] > 0:
                state["boss_alert_timer"] = max(0, state["boss_alert_timer"] - dt)

            if state["boss_active"] and state["boss"]:
                boss: Boss = state["boss"]
                boss.update(dt, state["boss_bullets"])
                state["boss_bullets"].update()

                for bullet in list(state["bullets"]):
                    if bullet.rect.colliderect(boss.rect):
                        bullet.kill()
                        sounds.play(sounds.boss_hit)
                        spawn_particles(
                            state["particles"],
                            bullet.rect.centerx,
                            bullet.rect.centery,
                            BOSS_COLOR,
                            4,
                        )
                        if boss.take_damage():
                            spawn_particles(
                                state["particles"],
                                boss.rect.centerx,
                                boss.rect.centery,
                                BOSS_COLOR,
                                24,
                            )
                            sounds.play(sounds.explosion)
                            maybe_drop_powerup(
                                state["powerups"], boss.rect.centerx, boss.rect.centery
                            )
                            maybe_drop_powerup(
                                state["powerups"],
                                boss.rect.centerx + 20,
                                boss.rect.centery,
                            )
                            boss.kill()
                            finish_boss_fight(state, sounds)

                if not player.invulnerable and pygame.sprite.spritecollide(
                    player, state["boss_bullets"], True
                ):
                    player_hit(state, sounds)

                if (
                    not player.invulnerable
                    and state["boss"]
                    and player.rect.colliderect(state["boss"].rect)
                ):
                    player_hit(state, sounds)
            else:
                state["enemies"].update()

                new_level = get_level(state["score"])
                if new_level > state["level"] and not state["boss_active"]:
                    start_boss_fight(state, new_level, diff, sounds)

                state["spawn_timer"] += dt
                interval = spawn_interval(state["level"], diff)
                cap = max_enemies(state["level"], diff)
                if state["spawn_timer"] >= interval and len(state["enemies"]) < cap:
                    state["spawn_timer"] = 0
                    state["enemies"].add(Enemy(state["level"], diff))

                for bullet in list(state["bullets"]):
                    hit = pygame.sprite.spritecollide(bullet, state["enemies"], False)
                    if hit:
                        bullet.kill()
                        sounds.play(sounds.hit)
                        for enemy in hit:
                            spawn_particles(
                                state["particles"],
                                enemy.rect.centerx,
                                enemy.rect.centery,
                                enemy.color,
                            )
                            maybe_drop_powerup(
                                state["powerups"],
                                enemy.rect.centerx,
                                enemy.rect.centery,
                            )
                            enemy.kill()
                            state["score"] += 10
                            if (
                                get_level(state["score"]) > state["level"]
                                and not state["boss_active"]
                            ):
                                start_boss_fight(
                                    state, get_level(state["score"]), diff, sounds
                                )
                                break

                if not player.invulnerable and pygame.sprite.spritecollide(
                    player, state["enemies"], True
                ):
                    player_hit(state, sounds)

            collected = pygame.sprite.spritecollide(player, state["powerups"], True)
            for pu in collected:
                sounds.play(sounds.powerup)
                spawn_particles(
                    state["particles"],
                    pu.rect.centerx,
                    pu.rect.centery,
                    POWERUP_COLORS[pu.kind],
                    14,
                )
                result = player.apply_powerup(pu.kind)
                if result == POWERUP_HEALTH and state["lives"] < 5:
                    state["lives"] += 1

        if (
            state["game_over"]
            and not state["name_saved"]
            and not state["entering_name"]
        ):
            if qualifies_for_highscore(state["score"], highscores):
                state["entering_name"] = True
                state["player_name"] = ""
            else:
                state["name_saved"] = True

        screen.fill(BG)
        draw_stars(screen, stars, star_offset)
        state["all_sprites"].draw(screen)
        state["bullets"].draw(screen)
        state["enemies"].draw(screen)
        state["powerups"].draw(screen)
        state["particles"].draw(screen)
        if state["boss"]:
            screen.blit(state["boss"].image, state["boss"].rect)
        state["boss_bullets"].draw(screen)
        draw_hud(screen, font, state)

        if state["paused"] and not state["game_over"]:
            draw_text(
                screen, big_font, "PAUSED", (WIDTH // 2, HEIGHT // 2), center=True
            )
            draw_text(
                screen,
                font,
                "Press P to resume",
                (WIDTH // 2, HEIGHT // 2 + 50),
                center=True,
            )

        if state["game_over"]:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))
            if state["entering_name"]:
                draw_text(
                    screen,
                    big_font,
                    "NEW RECORD!",
                    (WIDTH // 2, HEIGHT // 2 - 80),
                    ACCENT,
                    center=True,
                )
                draw_text(
                    screen,
                    font,
                    f"Score: {state['score']}",
                    (WIDTH // 2, HEIGHT // 2 - 30),
                    center=True,
                )
                draw_text(
                    screen,
                    font,
                    f"Enter name: {state['player_name']}_",
                    (WIDTH // 2, HEIGHT // 2 + 10),
                    center=True,
                )
                draw_text(
                    screen,
                    font,
                    "Enter — save   Esc — skip",
                    (WIDTH // 2, HEIGHT // 2 + 50),
                    (140, 150, 180),
                    center=True,
                )
            else:
                draw_text(
                    screen,
                    big_font,
                    "GAME OVER",
                    (WIDTH // 2, HEIGHT // 2 - 40),
                    (255, 100, 100),
                    center=True,
                )
                draw_text(
                    screen,
                    font,
                    f"Final score: {state['score']}  Level: {state['level']}",
                    (WIDTH // 2, HEIGHT // 2 + 10),
                    center=True,
                )
                if state["name_saved"]:
                    draw_text(
                        screen,
                        font,
                        "Score saved!",
                        (WIDTH // 2, HEIGHT // 2 + 45),
                        ACCENT,
                        center=True,
                    )
                draw_text(
                    screen,
                    font,
                    "Press R to restart   Esc — menu",
                    (WIDTH // 2, HEIGHT // 2 + 80),
                    center=True,
                )

        mute_label = "muted" if not sounds.enabled else "sound on"
        draw_text(
            screen,
            font,
            f"WASD — move   Space — shoot   P — pause   M — {mute_label}",
            (16, HEIGHT - 32),
            (120, 130, 160),
        )
        pygame.display.flip()

    sounds.stop_music()
    return "quit", highscores


def main():
    pygame.init()
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Star Dodger")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("menlo,consolas,monospace", 22)
    big_font = pygame.font.SysFont("menlo,consolas,monospace", 42, bold=True)
    stars = make_stars(80)
    sounds = Sounds()
    highscores = load_highscores()

    mode = "menu"
    selected_diff = "normal"

    while mode != "quit":
        if mode == "menu":
            draw_menu(screen, big_font, font, highscores)
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    mode = "quit"
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        mode = "quit"
                    elif event.key == pygame.K_h:
                        mode = "highscores"
                    elif event.key == pygame.K_1:
                        selected_diff = "easy"
                        mode = "game"
                    elif event.key == pygame.K_2:
                        selected_diff = "normal"
                        mode = "game"
                    elif event.key == pygame.K_3:
                        selected_diff = "hard"
                        mode = "game"
            clock.tick(FPS)
        elif mode == "highscores":
            draw_highscores(screen, big_font, font, highscores)
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    mode = "quit"
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_h):
                        mode = "menu"
            clock.tick(FPS)
        elif mode == "game":
            mode, highscores = run_game(
                screen, clock, font, big_font, stars, sounds, selected_diff, highscores
            )

    sounds.stop_music()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
