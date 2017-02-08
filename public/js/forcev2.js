function module() {

  // Private Properties and Attributes
  // ---------------------------------

  var vis,

      selectionChangedCallback,

      nodes,

      maxRadius = 30,

      // Separation between nodes
      padding = 6;


  // External Properties exposed through getter/setter
  // -------------------------------------------------

  // The currently selected items.
  var currentSelections = [];


  // Object to be Returned
  // ---------------------

  // Create a closure to manage the public attributes
  // and methods we want to expose. This function (which
  // will be the the return value for our component) is
  // the main function that callers will use to create a chart.

  // modified from http://bl.ocks.org/mbostock/1804919
  function chart (container, data, selectionCallback) {
    // Store a reference to the callback.
    selectionChangedCallback = selectionCallback;

    nodes = data;

    var width = 920,
      height = 400;

    var jobTitles = _.keys(_.groupBy(nodes, 'work_profession_group_name'));

    var x = d3.scale.ordinal()
        .domain(jobTitles)
        .rangePoints([0, width], 1),

        xPosition = function (d) {
          return x(d['work_profession_group_name']);
        },

        c = d3.scale.category10()
          .domain([0, jobTitles.length - 1]),

        color = function (d) {
          return c(d['work_profession_group_name']);
        },

        r = d3.scale.linear()
          .domain(d3.extent(nodes.map(function (d) {
            return d.count;
          })))
          .range([10, 40]),

        radius = function (d) {
          return r(d.count);
        };

    // set x positions
    nodes.forEach(function (d) {
      d._x = xPosition(d);
      d._y = 200;
      d._r = radius(d);
      d._color = color(d);
    });

    var force = d3.layout.force()
      .nodes(nodes)
      .size([width, height])
      .gravity(0)
      .charge(0)
      .on("tick", tick)
      .start();


    vis = d3.select(container);

    var svg = vis.selectAll('svg').data([nodes]);
    svg.enter()
      .append("svg")
      .attr("width", width)
      .attr("height", height);


    var state = svg.selectAll("g.state").data(function (d) {
      return d
    });
    state.enter().append("g").attr('class', 'state');
    state.exit().remove();

    var circle = state.selectAll('circle').data(function (d) {
      return [d]
    });
    circle.enter()
      .append('circle').attr('class', 'js-selectable-item')
      .on('click', function (d) {
        selectionChangedCallback([d]);
      });

    state.selectAll('circle')
      .attr("r", function (d) {
        return d._r
      })
      .style("fill", function (d) {
        return d._color
      })
      .style("stroke", '#fff')
      .attr("title", function (d) {
        return d.label;
      })
      .classed('active', isSelected);

    var text = state.selectAll('text').data(function (d) {
      return [d]
    });
    text.enter()
      .append('text')
      .style('pointer-events', 'none')
      .style('fill', 'white')
      .style('font-size', '10px')
      .style('text-anchor', 'middle')
      .attr('y', '5');

    state.selectAll('text').text(function (d) {
      return d.label.substr(0, 5);
    });

    var title = state.selectAll('title').data(function (d) {
      return [d]
    });

    title.enter().append('title');
    state.selectAll('title').text(function (d) {
      return d.label;
    });

    svg.selectAll("g.state").call(force.drag);


    var sectionTitle = svg.selectAll("text.section-title").data(jobTitles);
    sectionTitle.enter().append("text").attr('class', 'section-title');

    svg.selectAll('text.section-title')
      .attr('x', x)
      .attr('y', 100)
      .style('text-anchor', 'middle')
      .text(function (d) {
        return d;
      });

    sectionTitle.exit().remove();

  }

  function tick(e) {
    vis.selectAll("g.state")
      .each(gravity(.2 * e.alpha))
      .each(collide(.5))
      .attr('transform', function (d) {
        return 'translate(' + d.x + ',' + d.y + ')'
      });
  }

  // Move nodes toward cluster focus.
  function gravity(alpha) {
    return function (d) {
      d.y += (d._y - d.y) * alpha;
      d.x += (d._x - d.x) * alpha;
    };
  }

  // Resolve collisions between nodes.
  function collide(alpha) {
    var quadtree = d3.geom.quadtree(nodes);
    return function (d) {
      var r = d._r + maxRadius + padding,
        nx1 = d.x - r,
        nx2 = d.x + r,
        ny1 = d.y - r,
        ny2 = d.y + r;
      quadtree.visit(function (quad, x1, y1, x2, y2) {
        if (quad.point && (quad.point !== d)) {
          var x = d.x - quad.point.x,
            y = d.y - quad.point.y,
            l = Math.sqrt(x * x + y * y),
            r = d._r + quad.point._r + (d.color !== quad.point.color) * padding;
          if (l < r) {
            l = (l - r) / l * alpha;
            d.x -= x *= l;
            d.y -= y *= l;
            quad.point.x += x;
            quad.point.y += y;
          }
        }
        return x1 > nx2 || x2 < nx1 || y1 > ny2 || y2 < ny1;
      });
    };
  }

  // Check if `d` is selected.
  function isSelected(d) {
    return currentSelections.find((s) => s.id == d.id);
  }


  // Chart getter and setters
  // ------------------------

  chart.currentSelections = function(_a) {
    if (!arguments.length) return currentSelections;
    currentSelections = _a;
    return chart;
  };


  // Selections
  // -----------

  // Update the state of the selected items in the UI.
  chart.updateSelections = function() {
    vis.selectAll('circle')
      .classed('active', isSelected);
  };


  // Return the public attributes and methods
  return chart;
}