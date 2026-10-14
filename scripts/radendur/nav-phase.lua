-- nav-phase.lua -- Radical Enduro from boot to the starting line of the menu's first section, and one
-- photograph of it once the race is drawing: the race-start golden.
--
-- The section is confirmed by reading the game's state, not by counting frames, because a
-- mislabelled capture is worse than none. What the menu code (FUN_000f1878) holds:
--   0x20100c  screen state: 3 the selection screen, 4 racing
--   0x20100e  level (0..3)      0x20101a  segment (0..2)
--   START needs 0x20100a >= 0x10 (dwell) and two credits, writes 0x201014 = level*4 + segment (the
--   section) and moves to state 4.
-- It logs `START ok ... SECTION n` to OUT once the race starts in the section it expected, and
-- `SHOT startline` when it takes the photograph, then leaves the machine.
--
-- Env: OUT (the log).

local OUT = os.getenv("OUT") or "/tmp/navphase.txt"
local cpu = manager.machine.devices[":maincpu"]
local mem = cpu.spaces["program"]
local scr = manager.machine.screens[":screen"]
local p1 = manager.machine.ioport.ports[":P1"]
local coin, start = p1.fields["Coin 1"], p1.fields["1 Player Start"]

local ST_SCREEN, ST_LEVEL, ST_SEG, ST_SECTION, ST_DWELL = 0x20100c, 0x20100e, 0x20101a, 0x201014, 0x20100a
local EXC_LO, EXC_HI = 0x25a4, 0x25d8 -- the game's own exception handler

local log = io.open(OUT, "w")
local function say(fmt, ...)
    local s = string.format(fmt, ...)
    log:write(s .. "\n"); log:flush(); print(s)
end

-- 64 pixels spread over the screen: enough to tell whether the picture changed
local function screen_sig()
    local h = 0
    for gy = 0, 7 do
        for gx = 0, 7 do h = (h * 31 + scr:pixel(gx * 40 + 8, gy * 28 + 8)) % 0x7fffffff end
    end
    return h
end

local f, state, done, wait_from, drive_from, menu_sig = 0, "coin", false, 0, 0, 0
local want = 0
local function finish(reason)
    if done then return end
    done = true
    say("RESULT %s", reason)
    log:close()
    manager.machine:exit()
end

_G.nav = emu.add_machine_frame_notifier(function()
    if done then return end
    f = f + 1
    coin:set_value((f >= 240 and f <= 280) and 1 or 0) -- two credits, what a START costs
    local screen_state = mem:read_u16(ST_SCREEN)
    if state == "coin" then
        if f > 300 and screen_state == 3 then
            want = mem:read_u16(ST_LEVEL) * 4 + mem:read_u16(ST_SEG)
            state, wait_from = "start", f
        elseif f > 1200 then
            finish("ABORT: the menu (state 3) never appeared")
        end
    elseif state == "start" then
        if screen_state == 4 then
            start:set_value(0)
            local sec = mem:read_u16(ST_SECTION)
            if sec ~= want then return finish(string.format("ABORT: START gave section %d, expected %d", sec, want)) end
            say("START ok f=%d -> SECTION %d", f, sec)
            menu_sig, state, drive_from = screen_sig(), "startline", f
            return
        end
        if mem:read_u16(ST_DWELL) >= 0x10 then start:set_value(1) end
        if f - wait_from > 900 then finish("ABORT: START never started the race") end
    elseif state == "startline" then
        -- 0x20100c == 4 is not proof the race is alive (a hung 68000 leaves it at 4), so the cpu and
        -- the picture are watched until the photograph
        local pc = cpu.state["PC"].value
        if pc >= EXC_LO and pc <= EXC_HI then
            return finish(string.format("CRASH before drawing the race: pc=0x%06x", pc))
        end
        if f - drive_from == 240 then
            if screen_sig() == menu_sig then return finish("CRASH: still the menu 240 frames after START") end
            manager.machine.video:snapshot()
            say("SHOT startline f=%d", f)
            finish("starting-line capture taken")
        end
    end
end)
