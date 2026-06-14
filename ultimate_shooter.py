from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import sys
import os

app = Ursina()

window.title = "Ultimate 3D Shooter"
window.borderless = False

# -------------------------
# GAME VARIABLES
# -------------------------

kills = 0
wave = 1
player_health = 100

enemy_speed = 2
spawn_interval = 2

enemies = []
bullets = []
healthpacks = []

game_over = False

# -------------------------
# MAP
# -------------------------

ground = Entity(
    model='plane',
    scale=(60, 1, 60),
    texture='white_cube',
    texture_scale=(30, 30),
    color=color.gray
)

Sky()

for x in range(-30, 31, 5):
    Entity(model='cube', scale=(1, 3, 1), position=(x, 1.5, -30), color=color.dark_gray)
    Entity(model='cube', scale=(1, 3, 1), position=(x, 1.5,  30), color=color.dark_gray)

for z in range(-30, 31, 5):
    Entity(model='cube', scale=(1, 3, 1), position=(-30, 1.5, z), color=color.dark_gray)
    Entity(model='cube', scale=(1, 3, 1), position=( 30, 1.5, z), color=color.dark_gray)

# -------------------------
# PLAYER
# -------------------------

player = FirstPersonController(speed=6, jump_height=2)
player.cursor.color = color.red

# -------------------------
# UI
# -------------------------

health_text = Text(text='Health: 100', position=(-0.85, 0.45), scale=1.5)
kill_text   = Text(text='Kills: 0',    position=(-0.85, 0.40), scale=1.5)
wave_text   = Text(text='Wave: 1',     position=(-0.85, 0.35), scale=1.5)
message     = Text(text='', origin=(0, 0), scale=3)

# -------------------------
# BULLET
# -------------------------

class Bullet(Entity):
    def __init__(self):
        super().__init__(
            model='sphere',
            color=color.yellow,
            scale=0.15,
            position=camera.world_position,
        )
        self.direction = Vec3(camera.forward)
        self.dead = False  # guard flag so destroyed bullets aren't re-processed

    def update(self):
        if self.dead:
            return
        self.position += self.direction * 40 * time.dt
        if distance(self.position, player.position) > 100:
            self.dead = True
            destroy(self)

# -------------------------
# ENEMY
# -------------------------

class Enemy(Entity):
    def __init__(self, boss=False):
        super().__init__(
            model='cube',
            position=(
                random.uniform(-25, 25),
                1,
                random.uniform(-25, 25),
            )
        )
        self.boss = boss
        # Per-enemy hit cooldown prevents draining all health in one frame
        self.hit_cooldown = 0

        if boss:
            self.scale = 3
            self.color = color.orange
            self.health = 10
        else:
            self.scale = 1
            self.color = color.red
            self.health = 1

    def update(self):
        global player_health, game_over

        if game_over:
            return

        self.look_at(player)
        speed = enemy_speed * (2 if self.boss else 1)
        self.position += self.forward * speed * time.dt

        if self.hit_cooldown > 0:
            self.hit_cooldown -= 1

        if self.hit_cooldown == 0 and distance(self.position, player.position) < 1.5:
            player_health -= 10
            self.hit_cooldown = 60  # ~1 second before this enemy can hit again
            health_text.text = f'Health: {player_health}'

            # Knock back so it doesn't immediately re-trigger
            self.position += Vec3(
                random.uniform(-3, 3),
                0,
                random.uniform(-3, 3),
            )

            if player_health <= 0:
                end_game()

# -------------------------
# HEALTH PACK
# -------------------------

class HealthPack(Entity):
    def __init__(self):
        super().__init__(
            model='cube',
            color=color.lime,
            scale=0.7,
            position=(
                random.uniform(-25, 25),
                0.5,
                random.uniform(-25, 25),
            )
        )

# -------------------------
# FUNCTIONS
# -------------------------

def spawn_enemy():
    boss = (wave % 5 == 0)
    enemy = Enemy(boss)
    enemies.append(enemy)

def spawn_healthpack():
    pack = HealthPack()
    healthpacks.append(pack)

def next_wave():
    global wave, enemy_speed, spawn_interval

    wave += 1
    wave_text.text = f'Wave: {wave}'
    enemy_speed *= 1.15
    spawn_interval = max(0.5, spawn_interval * 0.95)

    message.text = f'WAVE {wave}'
    invoke(setattr, message, 'text', '', delay=1.5)

def end_game():
    global game_over

    if game_over:  # prevent being called multiple times in one frame
        return

    game_over = True
    mouse.locked = False
    message.text = f'GAME OVER\nKills: {kills}\nPress R To Restart'

def restart():
    # application.restart() is unreliable on Windows; re-exec the process instead
    os.execv(sys.executable, [sys.executable] + sys.argv)

# -------------------------
# INPUT
# -------------------------

def input(key):
    if key == 'left mouse down' and not game_over:
        Bullet()
    if key == 'r' and game_over:
        restart()

# -------------------------
# TIMERS
# -------------------------

def enemy_spawner():
    if not game_over:
        spawn_enemy()
        invoke(enemy_spawner, delay=spawn_interval)  # only reschedule while alive

enemy_spawner()

def healthpack_spawner():
    if not game_over:
        spawn_healthpack()
        invoke(healthpack_spawner, delay=15)

healthpack_spawner()

# -------------------------
# UPDATE
# -------------------------

def update():
    global kills, player_health  # declare ALL globals at the top — not mid-function

    if game_over:
        return

    # Bullet vs enemy collisions
    # Iterate a snapshot; skip bullets already marked dead
    for bullet in [e for e in scene.entities if isinstance(e, Bullet) and not e.dead]:
        for enemy in enemies[:]:
            if distance(bullet.position, enemy.position) < 1:
                enemy.health -= 1
                bullet.dead = True
                destroy(bullet)

                if enemy.health <= 0:
                    kills += 1
                    kill_text.text = f'Kills: {kills}'
                    enemies.remove(enemy)
                    destroy(enemy)

                    if kills % 10 == 0:
                        next_wave()

                break  # one bullet can only hit one enemy

    # Health pack pickup
    for pack in healthpacks[:]:
        if distance(player.position, pack.position) < 2:
            player_health = min(100, player_health + 25)
            health_text.text = f'Health: {player_health}'
            healthpacks.remove(pack)
            destroy(pack)

# -------------------------
# START MESSAGE
# -------------------------

message.text = "SURVIVE!"
invoke(setattr, message, 'text', '', delay=2)

app.run()
