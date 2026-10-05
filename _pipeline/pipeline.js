// Pipeline diagram ({{< pipeline ... >}}). Each .pl element carries its
// comparison or experiments as JSON (see _pipeline/sync.py), and its views as
// "<index of the JSON>:<plot>"; this lays out the stages, draws
// the path, and tracks the slide's fragments to move between states.
(function () {
  // Layout, in the 1500 x 680 coordinate space of .pl
  var W = 1500, H = 680, BOX_W = 240, HEAD_H = 56, OPT_TOP = 96;
  var OPT_H = 52, OPT_H2 = 76, MORE_H = 40, OPT_GAP = 14;
  var STACK_GAP = 40, GROUP_GAP = 6, LABEL_H = 22;
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
        var lines = o.label.split('\n');
        var opt = { id: o.id, col: col, x: x, y: y, h: lines.length > 1 || sub ? OPT_H2 : OPT_H };
        opt.el = div('pl-opt', x, y, BOX_W, opt.h);
        opt.el.style.setProperty('--col', col);
        lines.forEach(function (line, i) {
          if (i) opt.el.appendChild(document.createElement('br'));
          opt.el.appendChild(document.createTextNode(line));
        });
        if (sub) {
          var small = document.createElement('small');
          small.textContent = sub;
          opt.el.appendChild(small);
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
      }
      stage.label = div('pl-stack-label off', 2, 0);
      stage.label.textContent = stage.name;
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
    var top = H;
    var layouts = views.map(function (_, v) {
      var groups = stages.map(function (stage) {
        return stage.options.filter(function (o) { return chosenIn(v, stage.col, o.id); });
      });
      var boxes = 0, count = 0, m = 0;
      groups.forEach(function (group) {
        if (group.length) m++;
        group.forEach(function (o) { boxes += o.h; count++; });
      });
      var fixed = m * LABEL_H + (m - 1) * (STACK_GAP - LABEL_H) + (count - m) * GROUP_GAP;
      var s = Math.min(1, (H - fixed) / boxes);
      top = Math.min(top, Math.max(0, (H - fixed - boxes * s) / 2));
      return { s: s, y: {}, labels: [], groups: groups };
    });
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
          sy += opt.h * layout.s + GROUP_GAP;
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

    var prev = null;

    // State follows the number of visible step fragments, so it stays correct
    // when stepping backwards or arriving from a later slide.
    return function update() {
      var step = base + root.querySelectorAll('.pl-step.visible').length;
      var v = Math.max(0, Math.min(views.length - 1, step - n - 1));
      // Moving between plots of an already stacked slide: options slot in
      // and out sideways (see .pl.swap in pipeline.css)
      if (step !== prev) {
        root.classList.toggle('swap', prev !== null && prev > n && step > n);
        prev = step;
      }
      staged.forEach(function (st) { st.el.classList.toggle('shown', st.col <= step); });
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
        // Hidden options sit to the right of the stack if a later plot uses
        // them and to the left if an earlier one did
        opt.el.style.setProperty('--side', u > v ? 1 : u < v ? -1 : 0);
        opt.el.style.setProperty('--dx', -opt.x + 'px');
        opt.el.style.setProperty('--dy', (layout.y[opt.id] - opt.y) + 'px');
        opt.el.style.setProperty('--s', layout.s);
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

      // Once stacked, the slide title fades and the plot grows into its
      // space, and into the free space below the diagram
      var slide = root.closest('section');
      slide.classList.toggle('pl-notitle', step >= n + 1);
      if (root.offsetParent) {
        var below = Reveal.getConfig().height - root.offsetTop - H;
        root.style.setProperty('--above', Math.max(0, root.offsetTop - EDGE) + 'px');
        root.style.setProperty('--below', Math.max(0, below - EDGE_BOTTOM) + 'px');
      }
    };
  }

  document.addEventListener('DOMContentLoaded', function () {
    var updates = Array.prototype.map.call(document.querySelectorAll('.pl'), build);
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
