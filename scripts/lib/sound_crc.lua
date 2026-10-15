-- sound_crc.lua -- a CRC-32 of every word a CPU writes to its DACs over the first frames of a run, for
-- the goldens' sound check. The words are the game's own integers, so the number is the same on every
-- host, where MAME's mixed output goes through floating point.
--
--   sound_crc(cpu_tag, { addr, ... }, frames, out_path)
-- writes "crc=<8 hex> writes=<n>" to out_path once the frame counter reaches `frames`; a tap callback
-- that raises is counted, and any error makes the line say so instead of a CRC.
local function crc_table()
  local t = {}
  for i = 0, 255 do
    local c = i
    for _ = 1, 8 do c = (c & 1 ~= 0) and (0xedb88320 ~ (c >> 1)) or (c >> 1) end
    t[i] = c
  end
  return t
end

function sound_crc(cpu_tag, addrs, frames, out_path)
  local T = crc_table()
  local crc, writes, errors = 0xffffffff, 0, 0
  local function feed(byte) crc = T[(crc ~ byte) & 0xff] ~ (crc >> 8) end
  local screen = manager.machine.screens[":screen"]
  local space = manager.machine.devices[cpu_tag].spaces["program"]
  _G._sound_taps = {}
  for i, a in ipairs(addrs) do
    _G._sound_taps[i] = space:install_write_tap(a, a + 1, "sound" .. i, function(offset, data, mask)
      local ok = pcall(function()
        if screen:frame_number() < frames then
          writes = writes + 1
          feed(i); feed((data >> 8) & 0xff); feed(data & 0xff)
        end
      end)
      if not ok then errors = errors + 1 end
    end)
  end
  local done = false
  _G._sound_frames = emu.add_machine_frame_notifier(function()
    if done or screen:frame_number() < frames then return end
    done = true
    local out = io.open(out_path, "w")
    if errors > 0 then out:write(string.format("callback errors=%d\n", errors))
    else out:write(string.format("crc=%08x writes=%d\n", crc ~ 0xffffffff, writes)) end
    out:close()
  end)
end
