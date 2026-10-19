-- drive.lua -- inserts a coin, starts the game and DRIVES, never leaving the machine.
--
-- Any set of the family: coin, start, throttle and the digital steering are looked up under every
-- name the family gives them, plus the analogue accelerator where a board has one (Wheels & Fire,
-- whose wheel is analogue too and is left centred, so the car goes straight). Where the set has a
-- gear lever (Wheels & Fire's Gear Shift, a toggle), the pedal is the throttle and the lever is
-- pressed once into high as the driving starts.
--
-- It deliberately does not leave the machine (unlike nav-phase.lua, which calls machine:exit()
-- when its work is done): who decides when to stop is whoever is capturing, with -seconds_to_run.
--
-- Env: COIN_FRAME (200), START_FRAME (320), STEER=0 to go straight.
--      The frames are screen:frame_number()'s, the same ones that name the captures.

dofile((debug.getinfo(1, "S").source:match("^@(.*)/[^/]*$") or ".") .. "/lib/analog.lua")

local COIN_FRAME = tonumber(os.getenv("COIN_FRAME") or "200")
local START_FRAME = tonumber(os.getenv("START_FRAME") or "320")
local STEER = os.getenv("STEER") ~= "0"

local screen = manager.machine.screens[":screen"]
local p1 = manager.machine.ioport.ports[":P1"]
if not p1 then
    emu.print_error("__DRIVE INVALID: this system has no :P1 port")
    manager.machine:exit()
    return
end

-- Each control under every name the family uses for it: the field names differ from one game to
-- another, and a control that is missing is reported below as INVALID, never left untouched.
local function field(...)
    for _, n in ipairs({ ... }) do
        if p1.fields[n] then return p1.fields[n] end
    end
    return nil
end

local coin = field("Coin 1", "Coin")
local start = field("1 Player Start", "P1 Start", "Start 1")
local left = field("P1 Left")
local right = field("P1 Right")

-- The driving model, resolved once: what is floored to accelerate, and whether there is a gear to
-- shift. Where the set has a lever, the pedal is the accelerator (an analogue port of its own,
-- pressed to its maximum); elsewhere a button is, pressed.
local lever = p1.fields["Gear Shift"]
local accel, floor, accel_name
if lever then
    for _, port in pairs(manager.machine.ioport.ports) do
        accel = accel or port.fields["Accelerator Pedal"]
    end
    floor = accel and accel.maxvalue
    accel_name = "accelerator pedal"
else
    accel = field("P1 Button 1", "P1 Button 1 A", "Button 1")
    floor = 1
    accel_name = "throttle"
end

-- A list and not a table keyed by name: a nil value leaves its key out of a table constructor, so
-- `pairs` would never visit the very control that is missing.
for _, c in ipairs({ { "coin", coin }, { "start", start }, { accel_name, accel } }) do
    if not c[2] then
        emu.print_error(string.format("__DRIVE INVALID: control '%s' is missing", c[1]))
        manager.machine:exit()
        return
    end
end

-- A 40-frame press: plenty for the game to read it, and not so long that it counts twice.
local HOLD = 40
local DRIVE_FRAME = START_FRAME + HOLD

-- held over a window rather than for one frame, so a frame the game or a MAME menu misses cannot
-- lose it; a toggle flips once per press, so the lever goes to high once and stays there
local function held(f, from) return (f >= from and f < from + HOLD) and 1 or 0 end

_G._drive = emu.add_machine_frame_notifier(function()
    local f = screen:frame_number()
    coin:set_value(held(f, COIN_FRAME))
    start:set_value(held(f, START_FRAME))
    if f < DRIVE_FRAME then return end

    if accel.is_analog then analog_hold(accel, floor) else accel:set_value(floor) end
    if lever then lever:set_value(held(f, DRIVE_FRAME)) end
    -- A slow weave: going straight leaves the track almost at once, and a full turn every frame
    -- gives a trajectory no player makes, which leads to odd corners of the track.
    if STEER and left and right then
        local t = (f - START_FRAME) % 240
        left:set_value(t < 60 and 1 or 0)
        right:set_value((t >= 120 and t < 180) and 1 or 0)
    end
end)
