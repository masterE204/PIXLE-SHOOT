#!/usr/bin/env python3
"""
3D Shooter Game in Python using Ursina
Install dependencies: pip install ursina
"""

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import sys
import os

app = Ursina()
camera.position = (0, 8, 10)
camera.rotation = (0, 0, 0)

# Game variables
health = 100
kills = 0
level = 1
damage_cooldown = 0
shoot_cooldown = 0
shoot_cooldown_max = 0
last_level_up_kills = 0
enemy_speed = 0.05
bullet_speed = 0.4
game_over = False

KILLS_PER_LEVEL = 5
ARENA_BOUND = 24

bullets = []
enemies = []

# ============ SCENE ============

floor = Entity(
    model='quad',
    scale=(50, 1, 50),
    position=(0, -0.5, 0),
    color=color.dark_gray,
    texture='white_cube',
    collider='box',
)

player = Entity(
    model='cube',
    scale=(1, 1, 1),
    position=(0, 0.5, 0),
    color=color.green,
)

health_text    = Text(text=f'Health: {health}', position=(-0.85, 0.45))
kills_text     = Text(text=f'Kills: {kills}',   position=(-0.85, 0.40))
level_text     = Text(text=f'Level: {level}',   position=(-0.85, 0.35))
status_text    = Text(text='', origin=(0, 0), scale=3, color=color.white)

def update_camera():
    camera.position = (player.x, 8, player.z + 10)
    camera.look_at(player)

update_camera()

# ============ FUNCTIONS ============

def update_player_color():
    progress = min((kills - last_level_up_kills) / KILLS_PER_LEVEL, 1.0)
    # color.rgb expects 0-255 integers
    g = int((1.0 - progress) * 255)
    player.color = color.rgb(0, g, 0)

def level_up():
    global level, enemy_speed, shoot_cooldown_max, last_level_up_kills

    level += 1
    last_level_up_kills = kills
    enemy_speed *= 1.3
    shoot_cooldown_max = max(5, shoot_cooldown_max - 3)
    level_text.text = f'Level: {level}'

    # Show flash message then clear it — do NOT destroy the text entity
    status_text.text = 'LEVEL UP!'
    status_text.color = color.yellow
    invoke(setattr, status_text, 'text', '', delay=0.6)

def shoot():
    global shoot_cooldown

    if shoot_cooldown > 0 or game_over:
        return

    # Determine shoot direction from mouse hover on floor
    if mouse.world_point is not None:
        target = Vec3(mouse.world_point)
        direction = target - player.position
        direction.y = 0
        if direction.length() > 0:
            direction = direction.normalized()
        else:
            direction = Vec3(0, 0, -1)
    else:
        # Fallback: shoot toward nearest enemy or straight ahead
        if enemies:
            nearest = min(enemies, key=lambda e: distance(player.position, e.position))
            direction = (nearest.position - player.position)
            direction.y = 0
            if direction.length() > 0:
                direction = direction.normalized()
            else:
                direction = Vec3(0, 0, -1)
        else:
            direction = Vec3(0, 0, -1)

    bullet = Entity(
        model='sphere',
        scale=0.15,
        position=Vec3(player.position),
        color=color.yellow,
    )
    bullet.direction = direction
    bullet.alive = True
    bullets.append(bullet)
    shoot_cooldown = shoot_cooldown_max

def spawn_enemy():
    enemy = Entity(
        model='cube',
        scale=1,
        position=(random.uniform(-20, 20), 0.5, -20),
        color=color.red,
    )
    enemies.append(enemy)

def update_ui():
    health_text.text = f'Health: {health}'
    kills_text.text  = f'Kills: {kills}'
    level_text.text  = f'Level: {level}'

def show_game_over():
    status_text.text  = f'GAME OVER!\nKills: {kills}  Level: {level}\nPress R to Restart'
    status_text.color = color.red

# ============ INPUT ============

def input(key):
    if key in ('space', 'left mouse down'):
        shoot()
    if key == 'r' and game_over:
        os.execv(sys.executable, [sys.executable] + sys.argv)

# ============ MAIN LOOP ============

spawn_timer = 0

def update():
    global health, damage_cooldown, kills, shoot_cooldown, spawn_timer, game_over

    if game_over:
        return

    # Player movement
    speed = 0.1
    if held_keys['a'] or held_keys['left arrow']:  player.x -= speed
    if held_keys['d'] or held_keys['right arrow']: player.x += speed
    if held_keys['w'] or held_keys['up arrow']:    player.z -= speed
    if held_keys['s'] or held_keys['down arrow']:  player.z += speed

    player.x = max(-ARENA_BOUND, min(ARENA_BOUND, player.x))
    player.z = max(-ARENA_BOUND, min(ARENA_BOUND, player.z))

    update_camera()

    if shoot_cooldown > 0:  shoot_cooldown -= 1
    if damage_cooldown > 0: damage_cooldown -= 1

    # Enemy spawning — time.dt is a property, not a function
    spawn_timer += time.dt
    if spawn_timer >= 1.5:
        spawn_enemy()
        spawn_timer = 0

    # Move bullets + collision
    for bullet in bullets[:]:
        if not bullet.alive:
            continue
        bullet.position += bullet.direction * bullet_speed * time.dt * 60

        hit = False
        for enemy in enemies[:]:
            if distance(bullet.position, enemy.position) < 0.7:
                bullet.alive = False
                destroy(bullet)
                bullets.remove(bullet)
                destroy(enemy)
                enemies.remove(enemy)

                kills += 1
                update_player_color()
                update_ui()

                if kills - last_level_up_kills >= KILLS_PER_LEVEL:
                    level_up()

                hit = True
                break

        if not hit and bullet.alive and distance(bullet.position, player.position) > 100:
            bullet.alive = False
            destroy(bullet)
            bullets.remove(bullet)

    # Move enemies + damage
    for enemy in enemies[:]:
        dir_vec = player.position - enemy.position
        dir_vec.y = 0
        if dir_vec.length() > 0:
            dir_vec = dir_vec.normalized()
            enemy.position += dir_vec * enemy_speed * time.dt * 60

        if damage_cooldown <= 0 and distance(enemy.position, player.position) < 1.0:
            health -= 10
            damage_cooldown = 60
            update_ui()

            if health <= 0:
                game_over = True
                show_game_over()
                return

run()
