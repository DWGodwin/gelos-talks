// Pipeline diagram ({{< pipeline ... >}}). Each .pl element carries its
// comparison or experiments as JSON (see _pipeline/sync.py), and its views as
// "<index of the JSON>:<plot>"; this lays out the stages, draws
// the path, and tracks the slide's fragments to move between states.
// Config panels ({{< config ... >}}) are built here too: each .cfg element
// carries an excerpt as JSON (see _pipeline/excerpt.py).
(function () {
  // Layout, in the 1500 x 680 coordinate space of .pl
  var W = 1500, H = 680, BOX_W = 240, HEAD_H = 56, OPT_TOP = 96;
  var OPT_H = 52, OPT_H2 = 76, MORE_H = 40, OPT_GAP = 14;
  var STACK_GAP = 40, GROUP_GAP = 6, LABEL_H = 22;
  // Tool logos (see .pl-tools): the row's height, its gap under the tallest
  // stage, and the height the tools tied to an option add under that option
  // in the stack (.pl-opt-tools)
  var TOOLS_H = 60, TOOLS_GAP = 20, TOOL_TAG_H = 56;
  // Config lines (see .pl-cfg): font size, and the width a box leaves for one.
  // The font is monospace, with characters 0.6em wide.
  var CFG_PX = 14, CFG_W = BOX_W - 20, KEY_W = 18;
  // Config view (see .pl-config): where the plot area starts, the largest
  // font size, and the panel's metrics in em, which pipeline.css shares: row,
  // gap and file-name heights, vertical and horizontal padding, border.
  var VIEW_X = 310, VIEW_PX = 24;
  var ROW_EM = 1.45, GAP_EM = 0.55, FILE_EM = 2.2, PAD_EM = 0.9, PADX_EM = 1.2, BORDER = 2;
  var HEAD_EM = 2.6;
  // Space kept clear at the slide's top and bottom (slide number, logo) when
  // the plot expands
  var EDGE = 20, EDGE_BOTTOM = 56;
  var SVG_NS = 'http://www.w3.org/2000/svg';

  function tip(x, y) {
    return (x - 12) + ',' + (y - 7) + ' ' + x + ',' + y + ' ' + (x - 12) + ',' + (y + 7);
  }

  // Elbow connector with rounded corners, ending just short of the arrowhead
  function elbow(x1, y1, x2, y2) {
    var end = x2 - 10;
    if (Math.abs(y2 - y1) < 1) return 'M' + x1 + ' ' + y1 + 'H' + end;
    var mx = (x1 + x2) / 2, s = y2 > y1 ? 1 : -1;
    var r = Math.min(12, Math.abs(y2 - y1) / 2);
    return 'M' + x1 + ' ' + y1 + 'H' + (mx - r) +
      'Q' + mx + ' ' + y1 + ' ' + mx + ' ' + (y1 + s * r) +
      'V' + (y2 - s * r) +
      'Q' + mx + ' ' + y2 + ' ' + (mx + r) + ' ' + y2 + 'H' + end;
  }

  function span(cls, text, parent) {
    var el = document.createElement('span');
    el.className = cls;
    el.textContent = text;
    parent.appendChild(el);
    return el;
  }

  // An excerpt as a panel: the file's name over its rows, one element per
  // row. Returns the panel and its rows as { el, ids, chars }, gaps included.
  // An excerpt of several files (a diff) has a head row per file instead, and
  // a +/- column.
  function panel(excerpt) {
    var el = document.createElement('div');
    el.className = 'cfg-panel';
    if (excerpt.file) span('cfg-file', excerpt.file, el);
    var signed = excerpt.rows.some(function (row) { return row.sign; });
    var rows = excerpt.rows.map(function (row) {
      var line = document.createElement('div');
      el.appendChild(line);
      if (row.head) {
        line.className = 'cfg-head';
        span('cfg-head-file', row.head, line);
        var label = span('cfg-head-label', row.label, line);
        if (row.color) span('cfg-swatch', '', label).style.background = row.color;
        return { el: line, ids: [], head: true, chars: row.head.length + row.label.length + 8 };
      }
      if (row.gap) {
        line.className = 'cfg-gap';
        return { el: line, ids: [], gap: true };
      }
      line.className = 'cfg-row' + (row.ids ? ' tagged' : '')
        + (row.sign ? (row.sign === '+' ? ' add' : ' del') : '');
      if (signed) span('cfg-sign', (row.sign || ' ') + ' ', line);
      // "<indent and dash><key>:<value>"; a line without a key is all value
      var m = /^(\s*(?:- )?)([\w."'-]+:)(\s.*)?$/.exec(row.t) || [0, '', '', row.t];
      span('cfg-k', m[1] + m[2], line);
      var value = span('cfg-v', m[3] || '', line);
      var color = /"(#[0-9a-fA-F]{6})"/.exec(m[3] || '');
      if (color) span('cfg-swatch', '', value).style.background = color[1];
      if (row.c) span('cfg-c', '  ' + row.c, line);
      return { el: line, ids: row.ids || [], chars: line.textContent.length };
    });
    return { el: el, rows: rows, file: !!excerpt.file };
  }

  // Config panel ({{< config ... >}}): each click lights up the regions of
  // one step, and the slide's text that is tied to them (cfg="<region>")
  function config(root) {
    var built = panel(JSON.parse(root.querySelector('script').textContent));
    root.appendChild(built.el);
    var steps = root.dataset.steps ? root.dataset.steps.split(',') : [];
    var slide = root.closest('section');
    var tied = Array.prototype.map.call(slide.querySelectorAll('[data-cfg]'), function (el) {
      return { el: el.closest('li') || el, ids: el.dataset.cfg.split(/\s+/) };
    });
    tied.forEach(function (t) { t.el.classList.add('cfg-tied'); });

    return function update() {
      var k = root.querySelectorAll('.cfg-step.visible').length;
      var lit = k ? steps[k - 1].split('+') : [];
      function on(ids) {
        return ids.some(function (id) { return lit.indexOf(id) >= 0; });
      }
      root.classList.toggle('stepping', k > 0);
      built.rows.forEach(function (row) { row.el.classList.toggle('on', on(row.ids)); });
      tied.forEach(function (t) {
        t.el.classList.toggle('cfg-on', on(t.ids));
        t.el.classList.toggle('cfg-off', k > 0 && !on(t.ids));
      });
    };
  }

  function build(root) {
    var items = Array.prototype.map.call(
      root.querySelectorAll('script[type="application/json"]'),
      function (s) { return JSON.parse(s.textContent); });
    // The stage catalog is the same in every item
    var data = items[0];
    // One view per plot: the first is drawn as the path, later ones swap in
    var views = root.dataset.views.split(',').map(function (v) {
      var at = v.indexOf(':');
      return items[v.slice(0, at)].plots[v.slice(at + 1)];
    });
    var n = data.stages.length;
    var svg = root.querySelector('.pl-svg');
    var plot = root.querySelector('.pl-plot');
    var imgs = plot.querySelectorAll('img');
    // One line under the plot explaining its metric (labels.yml `caption`)
    var caption = document.createElement('div');
    caption.className = 'pl-caption';
    root.appendChild(caption);
    var colGap = (W - n * BOX_W) / (n - 1);
    // Steps already taken when the slide opens (start=stacked skips the build)
    var base = root.dataset.start === 'stacked' ? n + 1 : 0;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

    function div(cls, x, y, w, h) {
      var el = document.createElement('div');
      el.className = cls;
      el.style.left = x + 'px';
      el.style.top = y + 'px';
      if (w) el.style.width = w + 'px';
      if (h) el.style.height = h + 'px';
      root.insertBefore(el, plot);
      return el;
    }

    function shape(tag, cls, attrs, parent) {
      var el = document.createElementNS(SVG_NS, tag);
      if (cls) el.setAttribute('class', cls);
      for (var k in attrs) el.setAttribute(k, attrs[k]);
      (parent || svg).appendChild(el);
      return el;
    }

    function chosenIn(v, col, id) {
      return views[v].chosen[col].indexOf(id) >= 0;
    }

    // Draw every option that some view uses, then fill each stage up to
    // max_options in catalog order; the rest become "+ N more"
    var stages = data.stages.map(function (stage, col) {
      var used = stage.options.filter(function (o) {
        return views.some(function (_, v) { return chosenIn(v, col, o.id); });
      });
      var room = data.max_options - used.length;
      var shown = stage.options.filter(function (o) {
        return used.indexOf(o) >= 0 || room-- > 0;
      });
      return { name: stage.name, col: col, options: shown, more: stage.options.length - shown.length };
    });

    var staged = []; // elements revealed with each stage: { el, col }
    var byId = {};
    var stackable = [];
    var bottom = 0; // where the tallest stage's options end

    stages.forEach(function (stage) {
      var col = stage.col, x = col * (BOX_W + colGap);

      var head = div('pl-head', x, 0, BOX_W, HEAD_H);
      head.textContent = stage.name;
      staged.push({ el: head, col: col });

      if (col > 0) {
        var ax1 = x - colGap + 8, ax2 = x - 8, ay = HEAD_H / 2;
        var g = shape('g', 'pl-head-arrow', {});
        shape('line', '', { x1: ax1, y1: ay, x2: ax2 - 10, y2: ay }, g);
        shape('polygon', '', { points: tip(ax2, ay), stroke: 'none' }, g);
        staged.push({ el: g, col: col });
      }

      var y = OPT_TOP;
      stage.options = stage.options.map(function (o) {
        var sub = views.map(function (v) { return (v.subs || {})[o.id]; }).filter(Boolean)[0];
        // The config line that selects the option, which can differ per view
        var cfg = !sub && views.some(function (v) { return (v.lines || {})[o.id]; });
        var lines = o.label.split('\n');
        // h is the box's height in the diagram, with room for a config line;
        // hs its height in a stack too full to show config lines
        var opt = { id: o.id, col: col, x: x, y: y, hs: lines.length > 1 || sub ? OPT_H2 : OPT_H };
        opt.h = cfg ? OPT_H2 : opt.hs;
        opt.el = div('pl-opt', x, y, BOX_W);
        opt.el.style.setProperty('--h', opt.h + 'px');
        opt.el.style.setProperty('--col', col);
        lines.forEach(function (line, i) {
          if (i) opt.el.appendChild(document.createElement('br'));
          opt.el.appendChild(document.createTextNode(line));
        });
        if (sub || cfg) {
          var small = document.createElement('small');
          small.textContent = sub || '';
          opt.el.appendChild(small);
          if (cfg) {
            small.className = 'pl-cfg';
            opt.cfg = small;
          }
        }
        if (views.some(function (_, v) { return chosenIn(v, col, o.id); })) {
          opt.el.classList.add('stackable');
          opt.el.style.setProperty('--k', stackable.length);
          // Legend key: the option's line colors in the plot, if any
          opt.key = document.createElement('span');
          opt.key.className = 'pl-key';
          opt.el.appendChild(opt.key);
          if (views.some(function (v) { return (v.colors || {})[o.id]; })) {
            opt.el.classList.add('keyed');
          }
          stackable.push(opt);
        }
        byId[opt.id] = opt;
        staged.push({ el: opt.el, col: col });
        y += opt.h + OPT_GAP;
        return opt;
      });
      if (stage.more > 0) {
        var more = div('pl-more', x, y, BOX_W, MORE_H);
        more.textContent = '+ ' + stage.more + ' more';
        staged.push({ el: more, col: col });
        y += MORE_H;
      } else {
        y -= OPT_GAP;
      }
      bottom = Math.max(bottom, y);
      stage.label = div('pl-stack-label off', 2, 0);
      stage.label.textContent = stage.name;
    });

    // Tool logos (written by pipeline.lua from each stage's `tools`): one row
    // per stage, aligned under the tallest stage's options and revealed with
    // the stage. A row may spill into the gaps beside its column.
    var toolsY = Math.min(bottom + TOOLS_GAP, H - TOOLS_H);
    var tied = []; // tools tied to an option: { el, row, col, id }
    Array.prototype.forEach.call(root.querySelectorAll('.pl-tools'), function (row) {
      var col = parseInt(row.dataset.col, 10), x = col * (BOX_W + colGap);
      var pad = Math.max(0, (colGap - 10) / 2);
      row.style.left = (x - pad) + 'px';
      row.style.top = toolsY + 'px';
      row.style.width = (BOX_W + 2 * pad) + 'px';
      staged.push({ el: row, col: col });
      Array.prototype.forEach.call(row.querySelectorAll('.pl-tool[data-option]'), function (tool) {
        var opt = byId[tool.dataset.option];
        if (!opt) return;
        tied.push({ el: tool, row: row, col: col, id: opt.id });
        // The same tools hang in a row under their option once the options
        // stack (.pl-opt-tools, TOOL_TAG_H tall)
        if (!opt.tag) {
          opt.tag = document.createElement('div');
          opt.tag.className = 'pl-opt-tools';
          opt.el.appendChild(opt.tag);
        }
        var copy = tool.cloneNode(true);
        copy.classList.add('pl-opt-tool');
        copy.removeAttribute('data-option');
        opt.tag.appendChild(copy);
      });
    });

    // Path of the first view: one connector per [from, to] pair, grouped by
    // the gap it crosses
    views[0].links.forEach(function (pairs, g) {
      pairs.forEach(function (pair) {
        var a = byId[pair[0]], b = byId[pair[1]];
        if (!a || !b) return;
        var x1 = a.x + BOX_W + 4, y1 = a.y + a.h / 2;
        var x2 = b.x - 4, y2 = b.y + b.h / 2;
        shape('path', 'pl-link', { d: elbow(x1, y1, x2, y2), pathLength: 1 })
          .style.setProperty('--g', g);
        shape('polygon', 'pl-tip', { points: tip(x2, y2) })
          .style.setProperty('--g', g);
      });
    });

    // Stack layout per view: where each of its options lands on the left,
    // under a stage label. Stages the view doesn't use are left out, and the
    // boxes shrink together if the stack would be taller than the diagram.
    // An option with a tool tied to it keeps room for the tool under it.
    function tall(opt, height) {
      return opt[height] + (opt.tag ? TOOL_TAG_H : 0);
    }
    function stack(height) {
      return views.map(function (_, v) {
        var groups = stages.map(function (stage) {
          return stage.options.filter(function (o) { return chosenIn(v, stage.col, o.id); });
        });
        var boxes = 0, count = 0, m = 0;
        groups.forEach(function (group) {
          if (group.length) m++;
          group.forEach(function (o) { boxes += tall(o, height); count++; });
        });
        var fixed = m * LABEL_H + (m - 1) * (STACK_GAP - LABEL_H) + (count - m) * GROUP_GAP;
        var s = Math.min(1, (H - fixed) / boxes);
        return { s: s, y: {}, labels: [], groups: groups, top: Math.max(0, (H - fixed - boxes * s) / 2) };
      });
    }
    // Config lines stay in the stack only if every view's stack then fits
    // without shrinking; otherwise the boxes drop them (.pl.compact)
    var layouts = stack('h'), height = 'h';
    if (layouts.some(function (layout) { return layout.s < 1; })) {
      layouts = stack('hs');
      height = 'hs';
      root.classList.add('compact');
    }
    var top = Math.min.apply(null, layouts.map(function (layout) { return layout.top; }));
    // Every view starts at the top of the tallest one, so shared boxes stay
    // put when the plot changes
    layouts.forEach(function (layout) {
      var sy = top;
      layout.groups.forEach(function (group) {
        if (!group.length) return layout.labels.push(null);
        layout.labels.push(sy);
        sy += LABEL_H;
        group.forEach(function (opt) {
          layout.y[opt.id] = sy;
          sy += tall(opt, height) * layout.s + GROUP_GAP;
        });
        sy += STACK_GAP - LABEL_H - GROUP_GAP;
      });
    });

    // An option waits, hidden, at its place in the nearest view that uses it,
    // so it can slot in there rather than fly across the slide
    function nearestView(opt, v) {
      for (var d = 0; d < views.length; d++) {
        if (layouts[v + d] && opt.id in layouts[v + d].y) return v + d;
        if (layouts[v - d] && opt.id in layouts[v - d].y) return v - d;
      }
    }

    // Config view (config=yaml): the lines of the config behind the first
    // plot, shown in its place for one click once the options have stacked.
    // Every tagged row is lit, and linked to the stacked option it selects.
    // config=diff shows the first view's comparison diff the same way; its
    // rows aren't tagged, so it has no links.
    var cfg = null;
    if (root.dataset.config) {
      cfg = panel(root.dataset.config === 'diff'
        ? items[parseInt(root.dataset.views, 10)].diff : views[0].config);
      cfg.box = div('pl-config', 0, 0);
      cfg.box.appendChild(cfg.el);
      cfg.links = shape('g', 'pl-cfg-links', {});
      cfg.rows.forEach(function (row) { row.el.classList.toggle('on', row.ids.length > 0); });
    }

    // Size the panel to the free space (the plot area plus `above` and `below`
    // it), at the largest font that fits its rows and its longest line, and
    // draw a link from each stacked option to each run of rows tagged with it
    function fit(above, below) {
      if (cfg.fitted === above + ',' + below) return;
      cfg.fitted = above + ',' + below;
      var chars = 0, hEm = (cfg.file ? FILE_EM : 0) + 2 * PAD_EM;
      function em(row) { return row.gap ? GAP_EM : row.head ? HEAD_EM : ROW_EM; }
      cfg.rows.forEach(function (row) {
        hEm += em(row);
        chars = Math.max(chars, row.chars || 0);
      });
      var wEm = (chars + 1) * 0.6 + 2 * PADX_EM;
      var room = W - VIEW_X, tall = H + above + below;
      var px = Math.min(VIEW_PX, (tall - 2 * BORDER) / hEm, (room - 2 * BORDER) / wEm);
      var w = wEm * px + 2 * BORDER, h = hEm * px + 2 * BORDER;
      var x = VIEW_X + (room - w) / 2, y = (tall - h) / 2 - above;
      cfg.box.style.left = x + 'px';
      cfg.box.style.top = y + 'px';
      cfg.box.style.width = w + 'px';
      cfg.box.style.fontSize = px + 'px';

      cfg.links.textContent = '';
      var layout = layouts[0], runs = [];
      var at = y + BORDER + (PAD_EM + (cfg.file ? FILE_EM : 0)) * px;
      cfg.rows.forEach(function (row) {
        var rowH = em(row) * px, key = row.ids.join();
        var run = runs[runs.length - 1];
        if (key && run && run.open && run.key === key) run.y2 = at + rowH;
        else {
          if (run) run.open = false;
          if (key) runs.push({ key: key, ids: row.ids, y1: at, y2: at + rowH, open: true });
        }
        at += rowH;
      });
      runs.forEach(function (run) {
        run.ids.forEach(function (id) {
          var opt = byId[id];
          if (!opt || !(id in layout.y)) return;
          var x1 = BOX_W * layout.s + 6, y1 = layout.y[id] + opt[height] * layout.s / 2;
          var x2 = x - 6, y2 = (run.y1 + run.y2) / 2, mx = (x1 + x2) / 2;
          shape('path', '', {
            d: 'M' + x1 + ' ' + y1 + 'C' + mx + ' ' + y1 + ' ' + mx + ' ' + y2 + ' ' + x2 + ' ' + y2,
            pathLength: 1
          }, cfg.links);
          shape('circle', '', { cx: x2, cy: y2, r: 4 }, cfg.links);
        });
      });
    }

    var prev = null;

    // State follows the number of visible step fragments, so it stays correct
    // when stepping backwards or arriving from a later slide.
    return function update() {
      var step = base + root.querySelectorAll('.pl-step.visible').length;
      // The config view is one more step, between stacking and the first plot
      var showCfg = !!cfg && step === n + 1;
      var v = Math.max(0, Math.min(views.length - 1, step - n - 1 - (cfg ? 1 : 0)));
      // Moving between plots of an already stacked slide: options slot in
      // and out sideways (see .pl.swap in pipeline.css)
      if (step !== prev) {
        root.classList.toggle('swap', prev !== null && prev > n && step > n);
        prev = step;
      }
      staged.forEach(function (st) { st.el.classList.toggle('shown', st.col <= step); });
      // A tool tied to an option lights up, and the rest of its row dims,
      // while the path runs through that option
      tied.forEach(function (t) {
        var lit = step >= n && chosenIn(0, t.col, t.id);
        t.el.classList.toggle('lit', lit);
        t.row.classList.toggle('has-lit', lit);
      });
      stackable.forEach(function (opt) {
        var u = nearestView(opt, v), layout = layouts[u];
        opt.el.classList.toggle('chosen', u === v);
        // Colors follow the view the option sits in, so an option on its way
        // out keeps the key it had
        var colors = (views[u].colors || {})[opt.id] || [];
        if (opt.key.dataset.colors !== colors.join()) {
          opt.key.dataset.colors = colors.join();
          opt.key.textContent = '';
          colors.forEach(function (c) {
            var seg = document.createElement('span');
            seg.style.background = c;
            opt.key.appendChild(seg);
          });
        }
        if (opt.cfg) {
          var line = (views[u].lines || {})[opt.id] || '';
          var room = CFG_W - (opt.el.classList.contains('keyed') ? KEY_W : 0);
          opt.cfg.textContent = line;
          opt.cfg.style.fontSize = Math.min(CFG_PX, room / (line.length * 0.6)) + 'px';
        }
        // Hidden options sit to the right of the stack if a later plot uses
        // them and to the left if an earlier one did
        opt.el.style.setProperty('--side', u > v ? 1 : u < v ? -1 : 0);
        opt.el.style.setProperty('--dx', -opt.x + 'px');
        opt.el.style.setProperty('--dy', (layout.y[opt.id] - opt.y) + 'px');
        opt.el.style.setProperty('--s', layout.s);
        opt.el.style.setProperty('--hs', opt[height] + 'px');
      });
      stages.forEach(function (stage, i) {
        var y = layouts[v].labels[i];
        stage.label.classList.toggle('off', y === null);
        if (y !== null) stage.label.style.top = y + 'px';
      });
      Array.prototype.forEach.call(imgs, function (img, i) {
        img.classList.toggle('on', i === v);
      });
      var text = 'nocaption' in root.dataset ? '' : views[v].caption || '';
      caption.textContent = text;
      root.classList.toggle('captioned', !!text);
      root.classList.toggle('path', step >= n);
      root.classList.toggle('stacked', step >= n + 1);
      root.classList.toggle('config', showCfg);

      // Once stacked, the slide title fades and the plot grows into its
      // space, and into the free space below the diagram
      var slide = root.closest('section');
      slide.classList.toggle('pl-notitle', step >= n + 1);
      if (root.offsetParent) {
        var below = Reveal.getConfig().height - root.offsetTop - H;
        root.style.setProperty('--above', Math.max(0, root.offsetTop - EDGE) + 'px');
        root.style.setProperty('--below', Math.max(0, below - EDGE_BOTTOM) + 'px');
        if (cfg) fit(Math.max(0, root.offsetTop - EDGE), Math.max(0, below - EDGE_BOTTOM));
      }
    };
  }

  // Screen recordings ({{< clip ... >}}) are downloaded whole before they are
  // needed, one after another in deck order, and each video then plays from
  // its local copy, so a slow connection can't stall a clip mid-slide. The
  // tags are written with preload="none", so the browser doesn't also start
  // streaming them. A small counter at the bottom left shows the download's
  // progress (the title slide waits for a click, so wait there until it
  // clears); a clip whose download fails keeps its URL and streams as before.
  function preload() {
    var clips = Array.prototype.slice.call(document.querySelectorAll('video.clip[src]'));
    if (!clips.length || typeof fetch === 'undefined' || typeof URL.createObjectURL !== 'function') return;
    var note = document.createElement('div');
    note.id = 'clip-preload';
    document.body.appendChild(note);
    var done = 0, failed = 0;
    function show() {
      if (done + failed < clips.length) {
        note.textContent = 'loading clips ' + (done + failed + 1) + ' / ' + clips.length;
      } else if (failed) {
        note.textContent = failed + (failed > 1 ? ' clips' : ' clip') + ' not preloaded';
        note.classList.add('failed');
      } else {
        note.textContent = 'clips ready';
        setTimeout(function () { note.classList.add('done'); }, 3000);
        setTimeout(function () { note.remove(); }, 4500);
      }
    }
    function swap(v, blob) {
      // The clip may already be on screen, if the deck moved on while it
      // was downloading: carry its position over to the local copy
      var playing = !v.paused, at = v.currentTime;
      v.src = URL.createObjectURL(blob);
      v.preload = 'auto';
      if (at) v.currentTime = at;
      if (playing) v.play().catch(function () {});
    }
    function next(i) {
      if (i >= clips.length) { show(); return; }
      show();
      var v = clips[i];
      fetch(v.getAttribute('src'))
        .then(function (r) {
          if (!r.ok) throw new Error(r.status);
          return r.blob();
        })
        .then(function (blob) { swap(v, blob); done++; },
              function () { failed++; })
        .then(function () { next(i + 1); });
    }
    next(0);
  }

  document.addEventListener('DOMContentLoaded', function () {
    preload();
    var updates = Array.prototype.map.call(document.querySelectorAll('.pl'), build)
      .concat(Array.prototype.map.call(document.querySelectorAll('.cfg'), config));
    function update() {
      updates.forEach(function (u) { u(); });
    }
    function start() {
      update();
      // Screen recordings ({{< clip ... >}}) play from the top on each visit
      Reveal.on('slidechanged', function (e) {
        Array.prototype.forEach.call(e.currentSlide.querySelectorAll('video.clip'), function (v) {
          v.currentTime = 0;
        });
      });
      ['slidechanged', 'fragmentshown', 'fragmenthidden'].forEach(function (ev) {
        Reveal.on(ev, update);
      });
    }
    if (typeof Reveal === 'undefined') return;
    if (Reveal.isReady()) start();
    else Reveal.on('ready', start);
  });
})();
