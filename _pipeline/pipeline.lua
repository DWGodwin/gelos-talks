-- Animated pipeline diagram for gelos-lc plots. The data comes from
-- _pipeline/data/, written by `pixi run sync`.
--
--   {{< pipeline <comparison>:<plot> >}}
--   {{< pipeline <experiment>.<strategy>:<plot> <experiment>.<strategy>:<plot> ... >}}
--
-- Each argument is one view: a plot of a comparison, or of an experiment under
-- one extraction strategy. The pipeline is drawn for the first view; each view
-- after it adds a click that swaps the plot and the stacked options that
-- differ. Views are shown in the order given and may span lines.
-- `image=<path>` shows that image in place of a single view's own figure, e.g.
-- a screenshot of the app the plot's data feeds; the plot's caption is dropped.
-- `start=stacked` skips the build: the slide opens on the stacked options and
-- the first plot, leaving only the clicks that swap plots.
--
--   {{< clip videos/<name>.mp4 >}}
--
-- A looping, muted screen recording that restarts when its slide is shown; a
-- placeholder naming the path until the file exists.

local function read(path)
  local f = io.open(path, 'r')
  if not f then return nil end
  local s = f:read('a')
  f:close()
  return s
end

local function attr(s)
  return (s:gsub('&', '&amp;'):gsub('"', '&quot;'):gsub('<', '&lt;'))
end

local function dependency()
  quarto.doc.add_html_dependency({
    name = 'gelos-pipeline',
    version = '0.6.0',
    scripts = { 'pipeline.js' },
    stylesheets = { 'pipeline.css' },
  })
end

return {
  ['pipeline'] = function(args, kwargs)
    local root = quarto.project.directory

    local image = pandoc.utils.stringify(kwargs['image'] or '')
    if image ~= '' and #args > 1 then
      error('pipeline: image= replaces the figure of one view; pass a single <name>:<plot>')
    end

    local start = pandoc.utils.stringify(kwargs['start'] or '')
    if start ~= '' and start ~= 'stacked' then
      error('pipeline: start= takes "stacked", not "' .. start .. '"')
    end

    -- One view per argument, as "<data file index>:<plot>"; a data file that
    -- several views share is embedded once
    local index, files, scripts, imgs, views, data = {}, 0, '', '', {}, nil
    for i, arg in ipairs(args) do
      local view = pandoc.utils.stringify(arg)
      local name, plot = view:match('^([^:]+):([^:]+)$')
      if not name then
        error('pipeline: "' .. view .. '" should be <comparison>:<plot> or <experiment>.<strategy>:<plot>')
      end
      local text = read(root .. '/_pipeline/data/' .. name .. '.json')
      if not text then
        error('pipeline: no data for "' .. name .. '"; check the name and run `pixi run sync`')
      end
      local item = quarto.json.decode(text)
      if not index[name] then
        index[name] = files
        files = files + 1
        scripts = scripts .. '<script type="application/json">'
          .. (text:gsub('</', '<\\/')) .. '</script>'
      end
      local spec = item.plots[plot]
      if not spec then
        error('pipeline: "' .. name .. '" has no plot "' .. plot .. '"')
      end
      local src = image ~= '' and image or spec.image
      if not read(root .. '/' .. src) then
        error('pipeline: missing ' .. src .. (image ~= '' and '' or '; run `pixi run sync`'))
      end
      imgs = imgs .. '<img src="' .. attr(src) .. '" alt="'
        .. attr(item.title .. ': ' .. plot) .. '">'
      views[i] = index[name] .. ':' .. plot
      data = data or item
    end
    if not data then
      error('pipeline: pass at least one <name>:<plot>')
    end
    local count = #views

    dependency()

    -- One empty fragment per click: each later stage, the path, the stack,
    -- then each further plot. start=stacked keeps only the last of these.
    local clicks = start == 'stacked' and count - 1 or #data.stages + count
    local steps = string.rep('<span class="fragment pl-step"></span>', clicks)
    local html = '<div class="pl" data-views="' .. attr(table.concat(views, ',')) .. '"'
      .. (start ~= '' and ' data-start="' .. start .. '"' or '')
      .. (image ~= '' and ' data-nocaption' or '') .. '>'
      .. scripts
      .. '<svg class="pl-svg" aria-hidden="true"></svg>'
      .. '<div class="pl-plot">' .. imgs .. '</div>'
      .. steps .. '</div>'
    return pandoc.RawBlock('html', html)
  end,

  ['clip'] = function(args)
    local path = pandoc.utils.stringify(args[1] or '')
    dependency()
    if not read(quarto.project.directory .. '/' .. path) then
      return pandoc.RawBlock('html',
        '<div class="clip clip-missing">clip goes here<span>' .. attr(path) .. '</span></div>')
    end
    return pandoc.RawBlock('html',
      '<video class="clip" src="' .. attr(path) .. '" data-autoplay loop muted playsinline></video>')
  end
}
