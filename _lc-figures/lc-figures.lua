-- GELOS Land Cover dataset figures: where the chips are, and how many per class.
--
--   {{< lc-figure map >}}
--   {{< lc-figure classes >}}
--
-- Inlines _lc-figures/chip-map.svg or _lc-figures/class-distribution.svg, so
-- that the theme's colours reach into them, and loads lc-figures.css, which
-- colours and sizes them. The SVGs are written by `pixi run lc-figures`.

local FIGURES = {
  map = 'chip-map.svg',
  classes = 'class-distribution.svg',
}

return {
  ['lc-figure'] = function(args, kwargs)
    local which = pandoc.utils.stringify(args[1] or '')
    local file = FIGURES[which]
    if not file then
      error('lc-figure: takes "map" or "classes", not "' .. which .. '"')
    end
    local f = io.open(quarto.project.directory .. '/_lc-figures/' .. file, 'r')
    if not f then
      error('lc-figure: missing _lc-figures/' .. file .. '; run `pixi run lc-figures`')
    end
    local svg = f:read('a')
    f:close()

    quarto.doc.add_html_dependency({
      name = 'gelos-lc-figures',
      version = '0.1.0',
      stylesheets = { 'lc-figures.css' },
    })
    return pandoc.RawBlock('html', '<div class="lc-figure lc-figure-' .. which .. '">' .. svg .. '</div>')
  end
}
