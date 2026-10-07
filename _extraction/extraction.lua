-- Animated extraction figure: chips go into a model, tokens come out, and each
-- extraction strategy keeps some of them.
--
--   {{< extraction >}}
--
-- Inlines _extraction/extraction.svg, so that its layers can be Reveal
-- fragments, and loads extraction.css, which animates them. The SVG is written
-- by `pixi run extraction-figure`; one click per fragment index in it. Its
-- chip images are in images/lc-dataset/chips/, which _quarto.yml lists as a
-- resource because Quarto doesn't scan inline SVG.

return {
  ['extraction'] = function(args, kwargs)
    local f = io.open(quarto.project.directory .. '/_extraction/extraction.svg', 'r')
    if not f then
      error('extraction: missing _extraction/extraction.svg; run `pixi run extraction-figure`')
    end
    local svg = f:read('a')
    f:close()

    quarto.doc.add_html_dependency({
      name = 'gelos-extraction',
      version = '0.1.0',
      stylesheets = { 'extraction.css' },
    })
    return pandoc.RawBlock('html', '<div class="extraction">' .. svg .. '</div>')
  end
}
