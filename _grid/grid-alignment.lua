-- Animated grid-alignment figure: why chips are 960 m on a side.
--
--   {{< grid-alignment >}}
--   {{< grid-alignment start=patches >}}
--
-- Inlines _grid/grid-alignment.svg, so that its layers can be Reveal fragments,
-- and loads grid-alignment.css, which animates them. The SVG is written by
-- `pixi run grid-figure`; one click per fragment index in it.
-- `start=patches` skips the build: the slide opens with the pixel and patch
-- grids already drawn, leaving only the clicks that try each candidate chip.
-- `start=grids` opens with just the pixel grids.

-- start= value -> the class of the last layers that are shown from the start
local STARTS = { grids = 'pixels', patches = 'patches' }
local FRAGMENT = 'class="fragment custom ([^"]*)" data%-fragment%-index="(%d+)"'

return {
  ['grid-alignment'] = function(args, kwargs)
    local f = io.open(quarto.project.directory .. '/_grid/grid-alignment.svg', 'r')
    if not f then
      error('grid-alignment: missing _grid/grid-alignment.svg; run `pixi run grid-figure`')
    end
    local svg = f:read('a')
    f:close()

    local start = pandoc.utils.stringify(kwargs['start'] or '')
    if start ~= '' then
      local layer = STARTS[start]
      if not layer then
        error('grid-alignment: start= takes "grids" or "patches", not "' .. start .. '"')
      end
      -- The step at which the last of those layers appears...
      local last = 0
      for names, step in svg:gmatch(FRAGMENT) do
        if (' ' .. names .. ' '):find(' ' .. layer .. ' ', 1, true) then
          last = math.max(last, tonumber(step))
        end
      end
      -- ...and everything up to it is shown outright instead of being a fragment
      svg = svg:gsub(FRAGMENT, function(names, step)
        if tonumber(step) <= last then
          return 'class="' .. names .. ' visible"'
        end
      end)
    end

    quarto.doc.add_html_dependency({
      name = 'gelos-grid-alignment',
      version = '0.1.0',
      stylesheets = { 'grid-alignment.css' },
    })
    return pandoc.RawBlock('html', '<div class="grid-alignment">' .. svg .. '</div>')
  end
}
