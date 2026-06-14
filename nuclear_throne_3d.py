from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import sys
import os
import math

app = Ursina(title='Nuclear Throne 3D', borderless=False)
window.fps_counter.enabled = True

# ─────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────
ARENA = 28          # half-width of play area
CAM_HEIGHT = 22
CAM_TILT   = 18     # camera z-offset behind player

WEAPONS = {
    'pistol':    dict(damage=1,  cooldown=0.25, speed=30, spread=0.04, burst=1,  color=color.yellow,  ammo=999),
    'shotgun':   dict(damage=1,  cooldown=0.7,  speed=22, spread=0.18, burst=6,  color=color.orange,  ammo=40),
    'uzi':       dict(damage=1,  cooldown=0.07, speed=28, spread=0.10, burst=1,  color=color.cyan,    ammo=120),
    'launcher':  dict(damage=5,  cooldown=1.0,  speed=18, spread=0.01, burst=1,  color=color.red,     ammo=10),
    'laser':     dict(damage=3,  cooldown=0.4,  speed=50, spread=0.0,  burst=1,  color=color.lime,    ammo=30),
}

MUTATIONS = [
    dict(name='Strong Back',   desc='+1 max ammo on all guns', fn=lambda: boost_ammo(20)),
    dict(name='Rhino Skin',    desc='+1 max HP',               fn=lambda: boost_hp(1)),
    dict(name='Bloodlust',     desc='Kills heal 1 HP',         fn=lambda: enable_bloodlust()),
    dict(name='Eagle Eyes',    desc='Bullets go 30% faster',   fn=lambda: boost_bullet_speed(1.3)),
    dict(name='Trigger Fingers',desc='Fire 20% faster',        fn=lambda: boost_fire_rate(0.8)),
    dict(name='Bolt Marrow',   desc='Move 25% faster',         fn=lambda: boost_move_speed(1.25)),
]

# ─────────────────────────────────────────
# GAME STATE
# ─────────────────────────────────────────
hp          = 6
max_hp      = 6
kills       = 0
level       = 1
xp          = 0
xp_needed   = 10
wave        = 1
game_over   = False
bloodlust   = False
move_speed  = 7
bullet_spd_mult = 1.0
fire_rate_mult  = 1.0
active_mutations = []

current_weapon = 'pistol'
weapon_inventory = {'pistol': dict(**WEAPONS['pistol'])}  # deep copy ammo state
for w in weapon_inventory:
    weapon_inventory[w] = dict(**WEAPONS[w])

shoot_timer = 0

bullets   = []
enemies   = []
pickups   = []
particles = []
rooms_clear = 0

# ─────────────────────────────────────────
# SCENE
# ─────────────────────────────────────────
ground = Entity(
    model='plane', scale=(ARENA*2, 1, ARENA*2),
    texture='white_cube', texture_scale=(20,20),
    color=color.rgb(40,45,40), collider='box'
)

Sky(color=color.rgb(15,15,25))

# Walls
wall_data = [
    (0, 1.5, -ARENA,  ARENA*2, 3, 1),
    (0, 1.5,  ARENA,  ARENA*2, 3, 1),
    (-ARENA, 1.5, 0,  1, 3, ARENA*2),
    ( ARENA, 1.5, 0,  1, 3, ARENA*2),
]
for wx,wy,wz,wsx,wsy,wsz in wall_data:
    Entity(model='cube', position=(wx,wy,wz), scale=(wsx,wsy,wsz),
           color=color.rgb(60,60,70), collider='box')

# Random obstacle pillars
random.seed(42)
for _ in range(18):
    px = random.uniform(-ARENA+3, ARENA-3)
    pz = random.uniform(-ARENA+3, ARENA-3)
    if abs(px) < 4 and abs(pz) < 4:
        continue
    h = random.uniform(1.5, 3.5)
    Entity(model='cube', position=(px, h/2, pz),
           scale=(random.uniform(1,2.5), h, random.uniform(1,2.5)),
           color=color.rgb(55,55,65), collider='box')

# Ambient light
AmbientLight(color=color.rgba(80,80,100,255))
dl = DirectionalLight()
dl.look_at(Vec3(1,-2,1))

# ─────────────────────────────────────────
# PLAYER
# ─────────────────────────────────────────
player = Entity(
    model='cube', color=color.lime,
    scale=(0.8, 1.2, 0.8), position=(0, 0.6, 0),
    collider='box'
)
# Gun barrel visual
barrel = Entity(
    model='cube', color=color.dark_gray,
    scale=(0.15, 0.15, 0.6),
    parent=player
)
barrel.position = (0, 0.1, 0.7)

# Shadow circle under player
shadow = Entity(
    model='circle', color=color.rgba(0,0,0,80),
    scale=1.0, rotation_x=90, position=(0,-0.49,0),
    parent=player
)

# ─────────────────────────────────────────
# CAMERA (top-down angled)
# ─────────────────────────────────────────
camera.position = (0, CAM_HEIGHT, CAM_TILT)
camera.rotation_x = -55

# ─────────────────────────────────────────
# UI
# ─────────────────────────────────────────
# HP bar background
hp_bar_bg = Entity(model='quad', parent=camera.ui,
                   position=(-0.75,-0.44), scale=(0.32,0.035),
                   color=color.rgb(60,0,0), z=-1)
hp_bar    = Entity(model='quad', parent=camera.ui,
                   position=(-0.75,-0.44), scale=(0.32,0.035),
                   color=color.red, z=-2)
hp_text   = Text('HP: 6/6',   position=(-0.88,-0.42), scale=1.2, parent=camera.ui)
kill_text = Text('Kills: 0',  position=(-0.88,-0.46), scale=1.2, parent=camera.ui)
wave_text = Text('Wave: 1',   position=(-0.88,-0.50), scale=1.2, parent=camera.ui)
xp_text   = Text('XP: 0/10', position=(-0.88,-0.54), scale=1.2, parent=camera.ui)
gun_text  = Text('[ PISTOL | ∞ ]', position=(0.5,-0.46), scale=1.2, parent=camera.ui)
mut_text  = Text('', position=(-0.88, 0.38), scale=0.9, parent=camera.ui, color=color.yellow)

big_msg   = Text('', origin=(0,0), scale=3.5, parent=camera.ui, color=color.white)
sub_msg   = Text('', origin=(0,0), scale=1.5, parent=camera.ui,
                 color=color.light_gray, position=(0,-0.08))

crosshair_h = Entity(model='quad', parent=camera.ui, scale=(0.025,0.003), color=color.red, z=-1)
crosshair_v = Entity(model='quad', parent=camera.ui, scale=(0.003,0.025), color=color.red, z=-1)

def update_ui():
    hp_text.text  = f'HP: {hp}/{max_hp}'
    kill_text.text= f'Kills: {kills}'
    wave_text.text= f'Wave: {wave}'
    xp_text.text  = f'XP: {xp}/{xp_needed}'
    hp_bar.scale_x = max(0, (hp/max_hp)) * 0.32
    hp_bar.x = -0.75 - (0.32 - hp_bar.scale_x)/2
    w = current_weapon
    ammo = weapon_inventory[w]['ammo']
    ammo_str = '∞' if ammo >= 999 else str(ammo)
    gun_text.text = f'[ {w.upper()} | {ammo_str} ]'
    mut_text.text = '  '.join(active_mutations) if active_mutations else ''

# ─────────────────────────────────────────
# MUTATION HELPERS
# ─────────────────────────────────────────
def boost_ammo(n):
    for w in weapon_inventory:
        if weapon_inventory[w]['ammo'] < 999:
            weapon_inventory[w]['ammo'] += n

def boost_hp(n):
    global max_hp, hp
    max_hp += n
    hp = min(hp+n, max_hp)

def enable_bloodlust():
    global bloodlust
    bloodlust = True

def boost_bullet_speed(mult):
    global bullet_spd_mult
    bullet_spd_mult *= mult

def boost_fire_rate(mult):
    global fire_rate_mult
    fire_rate_mult *= mult

def boost_move_speed(mult):
    global move_speed
    move_speed *= mult

# ─────────────────────────────────────────
# WEAPON PICKUP DROP
# ─────────────────────────────────────────
WEAPON_NAMES = list(WEAPONS.keys())

def drop_weapon(pos):
    w = random.choice([k for k in WEAPON_NAMES if k != current_weapon])
    colors = dict(pistol=color.yellow, shotgun=color.orange, uzi=color.cyan,
                  launcher=color.red, laser=color.lime)
    p = Entity(model='cube', color=colors[w],
               scale=(0.6,0.25,0.6), position=(pos.x, 0.2, pos.z))
    p.weapon = w
    p.kind = 'weapon'
    p.bob_t = random.uniform(0, 6.28)
    pickups.append(p)

def drop_health(pos):
    p = Entity(model='sphere', color=color.red,
               scale=0.45, position=(pos.x, 0.3, pos.z))
    p.kind = 'health'
    p.bob_t = random.uniform(0, 6.28)
    pickups.append(p)

def drop_ammo(pos):
    p = Entity(model='cube', color=color.yellow,
               scale=0.35, position=(pos.x, 0.3, pos.z))
    p.kind = 'ammo'
    p.bob_t = random.uniform(0, 6.28)
    pickups.append(p)

# ─────────────────────────────────────────
# PARTICLES
# ─────────────────────────────────────────
def spawn_particles(pos, col, count=6):
    for _ in range(count):
        p = Entity(model='cube', color=col,
                   scale=random.uniform(0.08,0.18),
                   position=Vec3(pos))
        p.velocity = Vec3(
            random.uniform(-4,4),
            random.uniform(1,5),
            random.uniform(-4,4)
        )
        p.life = random.uniform(0.3, 0.7)
        particles.append(p)

# ─────────────────────────────────────────
# SHOOTING
# ─────────────────────────────────────────
def get_aim_dir():
    """Cast ray from camera through mouse to get aim direction on ground plane."""
    ray = camera.screen_to_world(mouse.position, distance=1)
    # Project ray onto y=0 plane from camera
    cam_pos = camera.world_position
    dir_vec  = (ray - cam_pos).normalized()
    if abs(dir_vec.y) < 0.001:
        return Vec3(0,0,-1)
    t = -cam_pos.y / dir_vec.y
    world_pt = cam_pos + dir_vec * t
    aim = Vec3(world_pt.x - player.x, 0, world_pt.z - player.z)
    if aim.length() < 0.01:
        return Vec3(0,0,-1)
    return aim.normalized()

def do_shoot():
    global shoot_timer
    w = weapon_inventory[current_weapon]
    cd = w['cooldown'] * fire_rate_mult
    if shoot_timer > 0 or (w['ammo'] <= 0 and w['ammo'] < 999):
        return
    aim = get_aim_dir()
    for _ in range(w['burst']):
        spread = w['spread']
        d = Vec3(
            aim.x + random.uniform(-spread, spread),
            0,
            aim.z + random.uniform(-spread, spread)
        ).normalized()
        b = Entity(
            model='sphere', color=w['color'],
            scale=0.18 if current_weapon != 'launcher' else 0.35,
            position=Vec3(player.x, 0.6, player.z) + d*0.9
        )
        b.velocity  = d * w['speed'] * bullet_spd_mult
        b.damage    = w['damage']
        b.life      = 2.5
        b.explosive = (current_weapon == 'launcher')
        b.dead      = False
        bullets.append(b)

    if w['ammo'] < 999:
        w['ammo'] -= 1
        if w['ammo'] <= 0:
            del weapon_inventory[current_weapon]
            switch_to_next_weapon()

    shoot_timer = cd
    update_ui()

def switch_to_next_weapon():
    global current_weapon
    available = list(weapon_inventory.keys())
    if available:
        current_weapon = available[0]
    update_ui()

# ─────────────────────────────────────────
# ENEMIES
# ─────────────────────────────────────────
class EnemyType:
    GOON    = 'goon'
    BRUTE   = 'brute'
    RANGER  = 'ranger'
    SPAWNER = 'spawner'

def spawn_enemy(etype=None):
    if etype is None:
        pool = [EnemyType.GOON]*5 + [EnemyType.BRUTE]*2 + [EnemyType.RANGER]*2
        if wave >= 3:
            pool += [EnemyType.SPAWNER]
        etype = random.choice(pool)

    # Spawn outside camera view but inside arena
    angle = random.uniform(0, math.pi*2)
    r = random.uniform(14, ARENA-2)
    ex = max(-ARENA+2, min(ARENA-2, player.x + math.cos(angle)*r))
    ez = max(-ARENA+2, min(ARENA-2, player.z + math.sin(angle)*r))

    if etype == EnemyType.GOON:
        e = Entity(model='cube', color=color.red,
                   scale=(0.9,1.1,0.9), position=(ex,0.55,ez))
        e.hp = 2; e.speed = 3.5 + wave*0.3; e.dmg = 1
        e.xp_val = 1
    elif etype == EnemyType.BRUTE:
        e = Entity(model='cube', color=color.orange,
                   scale=(1.5,1.8,1.5), position=(ex,0.9,ez))
        e.hp = 8; e.speed = 2.0 + wave*0.2; e.dmg = 2
        e.xp_val = 3
    elif etype == EnemyType.RANGER:
        e = Entity(model='cube', color=color.magenta,
                   scale=(0.7,1.0,0.7), position=(ex,0.5,ez))
        e.hp = 1; e.speed = 5.0 + wave*0.4; e.dmg = 1
        e.xp_val = 2
        e.shoot_timer = 0
    elif etype == EnemyType.SPAWNER:
        e = Entity(model='cube', color=color.violet,
                   scale=(2.0,2.0,2.0), position=(ex,1.0,ez))
        e.hp = 15; e.speed = 0.8; e.dmg = 1
        e.xp_val = 5
        e.spawn_timer = 0

    e.etype = etype
    e.hit_flash = 0
    e.base_color = e.color
    e.collider = 'box'
    enemies.append(e)

# Enemy bullets (rangers shoot back)
enemy_bullets = []

def enemy_shoot(e):
    d = Vec3(player.x - e.x, 0, player.z - e.z).normalized()
    b = Entity(model='sphere', color=color.magenta,
               scale=0.15, position=Vec3(e.x, 0.6, e.z) + d*1.2)
    b.velocity = d * 14
    b.life = 3.0
    b.dead = False
    enemy_bullets.append(b)

# ─────────────────────────────────────────
# WAVE SYSTEM
# ─────────────────────────────────────────
spawn_timer_val = 0
enemies_this_wave = 0
enemies_to_spawn  = 0

def start_wave():
    global enemies_to_spawn, enemies_this_wave
    enemies_to_spawn  = 6 + wave * 3
    enemies_this_wave = enemies_to_spawn
    wave_text.text = f'Wave: {wave}'
    big_msg.text  = f'WAVE {wave}'
    big_msg.color = color.yellow
    invoke(setattr, big_msg, 'text', '', delay=1.5)

start_wave()

# ─────────────────────────────────────────
# MUTATION SCREEN
# ─────────────────────────────────────────
choosing_mutation = False
mutation_choices  = []
mut_buttons       = []

def show_mutation_screen():
    global choosing_mutation, mutation_choices
    choosing_mutation = True
    mouse.locked = False

    choices = random.sample(MUTATIONS, min(3, len(MUTATIONS)))
    mutation_choices = choices

    big_msg.text  = 'LEVEL UP!  Choose a Mutation'
    big_msg.color = color.cyan
    big_msg.scale = 2.2

    for i, m in enumerate(choices):
        btn = Button(
            text=f'{m["name"]}\n{m["desc"]}',
            parent=camera.ui,
            scale=(0.35, 0.08),
            position=(0, 0.05 - i*0.12),
            color=color.rgb(30,60,80),
        )
        btn.mutation_index = i
        btn.on_click = lambda idx=i: pick_mutation(idx)
        mut_buttons.append(btn)

def pick_mutation(idx):
    global choosing_mutation, level
    m = mutation_choices[idx]
    m['fn']()
    active_mutations.append(m['name'])
    choosing_mutation = False

    for btn in mut_buttons:
        destroy(btn)
    mut_buttons.clear()

    big_msg.text  = ''
    big_msg.scale = 3.5
    mouse.locked = True
    update_ui()

# ─────────────────────────────────────────
# GAIN XP / LEVEL UP
# ─────────────────────────────────────────
def gain_xp(n):
    global xp, xp_needed, level
    xp += n
    if xp >= xp_needed:
        xp -= xp_needed
        xp_needed = int(xp_needed * 1.5)
        level += 1
        show_mutation_screen()
    update_ui()

# ─────────────────────────────────────────
# TAKE DAMAGE
# ─────────────────────────────────────────
player_iframes = 0  # invincibility frames after hit

def take_damage(dmg):
    global hp, player_iframes, game_over
    if player_iframes > 0 or game_over:
        return
    hp -= dmg
    player_iframes = 40
    player.color = color.white
    spawn_particles(player.position, color.red, 4)
    update_ui()
    if hp <= 0:
        end_game()

def end_game():
    global game_over
    game_over = True
    mouse.locked = False
    big_msg.text  = f'YOU DIED'
    big_msg.color = color.red
    sub_msg.text  = f'Kills: {kills}  |  Wave: {wave}  |  Level: {level}\nPress R to Restart'

# ─────────────────────────────────────────
# INPUT
# ─────────────────────────────────────────
def input(key):
    global current_weapon

    if game_over:
        if key == 'r':
            os.execv(sys.executable, [sys.executable] + sys.argv)
        return

    if choosing_mutation:
        return

    if key == 'left mouse down':
        do_shoot()

    # Weapon switching
    weapon_keys = {'1':'pistol','2':'shotgun','3':'uzi','4':'launcher','5':'laser'}
    if key in weapon_keys:
        wname = weapon_keys[key]
        if wname in weapon_inventory:
            current_weapon = wname
            update_ui()

    # Scroll wheel
    if key == 'scroll up' or key == 'scroll down':
        wlist = list(weapon_inventory.keys())
        if wlist:
            idx = wlist.index(current_weapon) if current_weapon in wlist else 0
            idx = (idx + (1 if key=='scroll up' else -1)) % len(wlist)
            current_weapon = wlist[idx]
            update_ui()

# ─────────────────────────────────────────
# EXPLOSION
# ─────────────────────────────────────────
def explode(pos):
    spawn_particles(pos, color.orange, 20)
    for enemy in enemies[:]:
        if distance(Vec3(pos), enemy.position) < 4:
            enemy.hp -= 4
            enemy.hit_flash = 5

# ─────────────────────────────────────────
# MAIN UPDATE
# ─────────────────────────────────────────
def update():
    global kills, xp, spawn_timer_val, enemies_to_spawn, wave, game_over
    global shoot_timer, player_iframes, hp

    if game_over or choosing_mutation:
        return

    dt = time.dt

    # ── Player movement ──────────────────
    move_dir = Vec3(0,0,0)
    if held_keys['w'] or held_keys['up arrow']:    move_dir.z -= 1
    if held_keys['s'] or held_keys['down arrow']:  move_dir.z += 1
    if held_keys['a'] or held_keys['left arrow']:  move_dir.x -= 1
    if held_keys['d'] or held_keys['right arrow']: move_dir.x += 1
    if held_keys['left mouse']:
        do_shoot()

    if move_dir.length() > 0:
        move_dir = move_dir.normalized()
        player.x = max(-ARENA+1, min(ARENA-1, player.x + move_dir.x * move_speed * dt))
        player.z = max(-ARENA+1, min(ARENA-1, player.z + move_dir.z * move_speed * dt))

    # Rotate player to face aim direction
    aim = get_aim_dir()
    if aim.length() > 0:
        angle = math.degrees(math.atan2(aim.x, aim.z))
        player.rotation_y = angle

    # ── Camera follow ─────────────────────
    camera.position = Vec3(
        lerp(camera.x, player.x, dt*6),
        CAM_HEIGHT,
        lerp(camera.z, player.z + CAM_TILT, dt*6)
    )

    # ── Shoot cooldown ────────────────────
    if shoot_timer > 0:
        shoot_timer = max(0, shoot_timer - dt)

    # ── Player iframe flash ───────────────
    if player_iframes > 0:
        player_iframes -= 1
        player.color = color.white if player_iframes % 6 < 3 else color.lime
        if player_iframes == 0:
            player.color = color.lime

    # ── Spawn enemies ─────────────────────
    if enemies_to_spawn > 0:
        spawn_timer_val += dt
        interval = max(0.4, 1.5 - wave*0.1)
        if spawn_timer_val >= interval:
            spawn_enemy()
            enemies_to_spawn -= 1
            spawn_timer_val = 0

    # ── Check wave clear ──────────────────
    if enemies_to_spawn == 0 and len(enemies) == 0:
        wave += 1
        start_wave()
        # Bonus health pack every wave
        drop_health(Vec3(random.uniform(-10,10), 0, random.uniform(-10,10)))

    # ── Move bullets ──────────────────────
    for b in bullets[:]:
        if b.dead:
            continue
        b.position += b.velocity * dt
        b.life -= dt

        hit = False
        for e in enemies[:]:
            if distance(b.position, e.position) < (e.scale_x * 0.7):
                e.hp -= b.damage
                e.hit_flash = 6
                b.dead = True
                if b.explosive:
                    explode(b.position)
                destroy(b)
                bullets.remove(b)
                hit = True

                if e.hp <= 0:
                    spawn_particles(e.position, e.base_color, 10)
                    gain_xp(e.xp_val)
                    kills += 1
                    kill_text.text = f'Kills: {kills}'
                    if bloodlust:
                        hp = min(max_hp, hp+1)
                        update_ui()
                    # Random drop
                    roll = random.random()
                    if roll < 0.12:
                        drop_weapon(e.position)
                    elif roll < 0.30:
                        drop_health(e.position)
                    elif roll < 0.50:
                        drop_ammo(e.position)
                    enemies.remove(e)
                    destroy(e)
                break

        if not hit and b.life <= 0:
            b.dead = True
            destroy(b)
            if b in bullets:
                bullets.remove(b)

    # ── Enemy bullets ─────────────────────
    for b in enemy_bullets[:]:
        if b.dead:
            continue
        b.position += b.velocity * dt
        b.life -= dt
        if distance(b.position, player.position) < 0.7:
            take_damage(1)
            b.dead = True
            destroy(b)
            enemy_bullets.remove(b)
        elif b.life <= 0:
            b.dead = True
            destroy(b)
            enemy_bullets.remove(b)

    # ── Update enemies ────────────────────
    for e in enemies[:]:
        if not e or not e.enabled:
            continue

        # Hit flash
        if e.hit_flash > 0:
            e.hit_flash -= 1
            e.color = color.white if e.hit_flash % 3 == 0 else e.base_color
        else:
            e.color = e.base_color

        to_player = Vec3(player.x - e.x, 0, player.z - e.z)
        dist = to_player.length()

        if dist > 0:
            e.position += (to_player.normalized() * e.speed * dt)
            e.position = Vec3(
                max(-ARENA+1, min(ARENA-1, e.x)),
                e.y,
                max(-ARENA+1, min(ARENA-1, e.z))
            )

        # Type-specific behavior
        if e.etype == EnemyType.RANGER:
            e.shoot_timer -= dt
            if dist < 18 and e.shoot_timer <= 0:
                enemy_shoot(e)
                e.shoot_timer = 2.0

        elif e.etype == EnemyType.SPAWNER:
            e.spawn_timer -= dt
            if e.spawn_timer <= 0:
                spawn_enemy(EnemyType.GOON)
                e.spawn_timer = 4.0

        # Melee damage
        if dist < 1.2:
            take_damage(e.dmg)

    # ── Pickups ───────────────────────────
    for p in pickups[:]:
        p.bob_t += dt * 2
        p.y = 0.25 + math.sin(p.bob_t) * 0.1
        p.rotation_y += dt * 90

        if distance(Vec3(player.x, 0, player.z), Vec3(p.x, 0, p.z)) < 1.2:
            if p.kind == 'health':
                if hp < max_hp:
                    hp = min(max_hp, hp+1)
                    update_ui()
                    spawn_particles(p.position, color.red)
                    pickups.remove(p)
                    destroy(p)
            elif p.kind == 'ammo':
                wn = current_weapon
                if weapon_inventory[wn]['ammo'] < 999:
                    weapon_inventory[wn]['ammo'] += 15
                    update_ui()
                spawn_particles(p.position, color.yellow)
                pickups.remove(p)
                destroy(p)
            elif p.kind == 'weapon':
                wname = p.weapon
                weapon_inventory[wname] = dict(**WEAPONS[wname])
                current_weapon = wname
                spawn_particles(p.position, color.cyan)
                pickups.remove(p)
                destroy(p)
                update_ui()

    # ── Particles ─────────────────────────
    for p in particles[:]:
        p.position += p.velocity * dt
        p.velocity.y -= 12 * dt  # gravity
        p.life -= dt
        p.alpha = max(0, p.life)
        if p.life <= 0:
            particles.remove(p)
            destroy(p)

    update_ui()

# ─────────────────────────────────────────
# LOCK MOUSE
# ─────────────────────────────────────────
mouse.locked = True
mouse.visible = False

# Crosshair tracks mouse position
def late_update():
    # Keep crosshair centered (we use fixed crosshair)
    pass

app.run()
