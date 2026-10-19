-- analog.lua -- holds an analog input at the value its port reads, for the harnesses that drive one.
--
--   analog_hold(field, value)
-- A value set from Lua goes through the field's PORT_INVERT from MAME's bcb82ffcd68 on and not before
-- it (src/emu/ioport.cpp, analog_field::read), so it is set, read back off the port, and set inverted
-- within the field's range when the port reads something else. The value has to be in the field's
-- range: out of it, the clamp would read as an inversion.
function analog_hold(field, value)
  field:set_value(value)
  local shift = 0
  while ((field.mask >> shift) & 1) == 0 do shift = shift + 1 end
  if ((field.port:read() & field.mask) >> shift) ~= value then
    field:set_value(field.minvalue + field.maxvalue - value)
  end
end
