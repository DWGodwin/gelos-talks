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
-- `config=yaml` adds a click before the first plot: once the options stack,
-- the plot's place is taken by the lines of the config behind it, each stacked
-- option linked to the lines that select it; the next click shows the plot.
-- `config=diff`, for a comparison, shows instead what sets its experiments
-- apart: under each one's file name, the config lines that differ from the
-- control's. Only comparisons whose experiments differ by a few lines have one.
-- Each stage draws the logos of the tools it lists in labels.yml under its
-- options; `tools=<key>,<key>,...` (keys of the labels.yml tool catalog) draws
-- a row of logos under the plot as well, e.g. the tools that feed an app.
--
--   {{< config <excerpt> <regions> <regions> ... >}}
--
-- A panel of YAML cut from a real config: an excerpt from
-- _pipeline/excerpts.yml, also written by `pixi run sync`. Each argument after
-- the name adds a click that lights up one region of the excerpt, or several
-- joined with + (`lulc+chips`); with none, the panel is static. Text on the
-- same slide follows along: a span with cfg="<region>" is lit with its region
-- and dimmed while another one is. `size=<px>` sets the font size.
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
    version = '0.9.0',
    scripts = { 'pipeline.js' },
    stylesheets = { 'pipeline.css' },
  })
end

-- One tool as a logo (or a text badge when it has none) over a small caption:
-- its name, unless labels.yml gives a caption. A tool tied to an option
-- carries the option's id, for pipeline.js to light it up and stack it.
local function tool_html(tool, root)
  local cls = 'pl-tool' .. (tool.pill and ' pill' or '') .. (tool.logo and '' or ' badge')
  local html = '<span class="' .. cls .. '" title="' .. attr(tool.name) .. '"'
    .. (tool.option and ' data-option="' .. attr(tool.option) .. '"' or '') .. '>'
  if tool.logo then
    if not read(root .. '/' .. tool.logo) then
      error('pipeline: missing logo ' .. tool.logo .. ' for "' .. tool.name .. '"')
    end
    -- The height is written on the element too, so a large logo file never
    -- shows at its own size before the stylesheet applies (LOGO_H in
    -- pipeline.css)
    html = html .. '<img src="' .. attr(tool.logo) .. '" alt="' .. attr(tool.name) .. '" height="40">'
  else
    html = html .. '<span class="pl-badge">' .. attr(tool.name) .. '</span>'
  end
  if tool.logo or tool.caption then
    html = html .. '<small>' .. attr(tool.caption or tool.name) .. '</small>'
  end
  return html .. '</span>'
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

    local config = pandoc.utils.stringify(kwargs['config'] or '')
    if config ~= '' and config ~= 'yaml' and config ~= 'diff' then
      error('pipeline: config= takes "yaml" or "diff", not "' .. config .. '"')
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
      if i == 1 and config == 'yaml' and not spec.config then
        error('pipeline: no config excerpt for "' .. view .. '"; run `pixi run sync`')
      end
      if i == 1 and config == 'diff' and not item.diff then
        error('pipeline: "' .. name .. '" has no diff: it is not a comparison, or its '
          .. 'experiments differ by too much to show (or run `pixi run sync`)')
      end
      data = data or item
    end
    if not data then
      error('pipeline: pass at least one <name>:<plot>')
    end
    local count = #views

    -- The tools each stage is built on, as a row of logos under its options
    -- (empty for a stage without any), and the slide's own row under the plot
    local rows = ''
    for i, stage in ipairs(data.stages) do
      if stage.tools and #stage.tools > 0 then
        rows = rows .. '<div class="pl-tools" data-col="' .. (i - 1) .. '">'
        for _, tool in ipairs(stage.tools) do rows = rows .. tool_html(tool, root) end
        rows = rows .. '</div>'
      end
    end
    local app = ''
    local tools = pandoc.utils.stringify(kwargs['tools'] or '')
    if tools ~= '' then
      local text = read(root .. '/_pipeline/data/tools.json')
      if not text then
        error('pipeline: no _pipeline/data/tools.json; run `pixi run sync`')
      end
      local catalog = quarto.json.decode(text)
      app = '<div class="pl-app-tools">'
      for key in tools:gmatch('[^,]+') do
        if not catalog[key] then
          error('pipeline: tools= names "' .. key .. '", which is not in the labels.yml tool catalog')
        end
        app = app .. tool_html(catalog[key], root)
      end
      app = app .. '</div>'
    end

    dependency()

    -- One empty fragment per click: each later stage, the path, the stack,
    -- then each further plot. start=stacked keeps only the last of these, and
    -- a config view adds one.
    local clicks = (start == 'stacked' and count - 1 or #data.stages + count)
      + (config ~= '' and 1 or 0)
    local steps = string.rep('<span class="fragment pl-step"></span>', clicks)
    local html = '<div class="pl" data-views="' .. attr(table.concat(views, ',')) .. '"'
      .. (start ~= '' and ' data-start="' .. start .. '"' or '')
      .. (config ~= '' and ' data-config="' .. config .. '"' or '')
      .. (image ~= '' and ' data-nocaption' or '')
      .. (app ~= '' and ' data-tooled' or '') .. '>'
      .. scripts
      .. '<svg class="pl-svg" aria-hidden="true"></svg>'
      .. rows
      .. '<div class="pl-plot">' .. imgs .. '</div>'
      .. app
      .. steps .. '</div>'
    return pandoc.RawBlock('html', html)
  end,

  ['config'] = function(args, kwargs)
    local name = pandoc.utils.stringify(args[1] or '')
    if name == '' then
      error('config: pass the name of an excerpt from _pipeline/excerpts.yml')
    end
    local text = read(quarto.project.directory .. '/_pipeline/data/excerpts/' .. name .. '.json')
    if not text then
      error('config: no excerpt "' .. name .. '"; check _pipeline/excerpts.yml and run `pixi run sync`')
    end
    local regions = {}
    for _, row in ipairs(quarto.json.decode(text).rows) do
      for _, id in ipairs(row.ids or {}) do regions[id] = true end
    end
    local steps = {}
    for i = 2, #args do
      local step = pandoc.utils.stringify(args[i])
      for region in step:gmatch('[^+]+') do
        if not regions[region] then
          error('config: excerpt "' .. name .. '" has no region "' .. region .. '"')
        end
      end
      steps[#steps + 1] = step
    end
    local size = pandoc.utils.stringify(kwargs['size'] or '')
    if size ~= '' and not size:match('^%d+$') then
      error('config: size= takes a font size in px, not "' .. size .. '"')
    end

    dependency()

    return pandoc.RawBlock('html',
      '<div class="cfg" data-steps="' .. attr(table.concat(steps, ',')) .. '"'
      .. (size ~= '' and ' style="font-size: ' .. size .. 'px"' or '') .. '>'
      .. '<script type="application/json">' .. (text:gsub('</', '<\\/')) .. '</script>'
      .. string.rep('<span class="fragment cfg-step"></span>', #steps) .. '</div>')
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
