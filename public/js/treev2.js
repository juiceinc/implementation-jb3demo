// Module Definition
// -----------------
function module() {

  // Private Properties and Attributes
  // ---------------------------------

  var vis,

      width,

      height,

      depthWidth,

      selectionChangedCallback,

      MAX_DEPTH = 4,

      margin = {top: 20, right: 120, bottom: 20, left: 120},

      pctFormatter = d3.format(',.0%'),

      duration = 750,

      root,

      valueFx = function (d) {
        return d.value;
      },

      codeFx = function (d) {
        return d.code;
      },

      idFx = function (d) {
        return d.action_id;
      },

      tree = d3.layout.tree(),

      diagonal = d3.svg.diagonal()
        .projection(function (d) {
          return [d.y, d.x];
        });

  //Red if score 64.99 or below
  //Orange if score between 65 and 74.99
  //Yellow if score between 75 and 84.99
  //Light Green if score between 85 and 94.99
  //Green if score 95 or above
  //(Incomplete stay gray.)

  var domainValues = [0, 0.0000000001, 0.6500, 0.7500, 0.8500, 0.9500, 1],

      c1 = d3.scale.quantile()
        .domain(domainValues)
        .range(['#ccc', '#CA271E', '#F06E4F', '#FCC050', '#B1D55F', '#50B053']),

      fillColor = function (d) {
        return c1(valueFx(d));
      },

      c2 = d3.scale.quantile()
        .domain(domainValues)
        .range(['#666', '#CA271E', '#F06E4F', '#FCC050', '#B1D55F', '#50B053']),

      strokeColor = function (d) {
        return c2(valueFx(d));
      },

      r = d3.scale.linear()
        .range([5, 20]),

      radius = function (d) {
        return 15;
      };

  var options = [
    {key: 'code', option: 'Code'},
    {key: 'action_id', option: 'Action Id'},
    {key: 'metric value', option: 'Score'}
  ];


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

  function chart(container, data, selectionCallback) {
    // Store a reference to the callback.
    selectionChangedCallback = selectionCallback;

    width = 1170 - margin.right - margin.left;
    height = 800 - margin.top - margin.bottom;

    depthWidth = width / MAX_DEPTH;

    tree
      .size([height, width]).sort(function (a, b) {
        if (codeFx(a) < codeFx(b)) return -1;
        if (codeFx(a) > codeFx(b)) return 1;
        return 0;
      });

    vis = d3.select(container);
    var svgEnter = vis.selectAll('svg').data([{}])
        .enter()
        .append("svg")
        .attr("width", width + margin.right + margin.left)
        .attr("height", height + margin.top + margin.bottom)
        .style("margin-top", '20px');

    // background gridlines
    svgEnter
        .append("g")
        .attr('class', 'tree-background')
        .attr("transform", "translate(" + (margin.left - depthWidth / 2) + "," + margin.top + ")");

    // tree container
    svgEnter
        .append("g")
        .attr('class', 'tree-container')
        .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

    var svg = vis.selectAll('g.tree-container');

    root = data[0];
    root.x0 = height / 2;
    root.y0 = 0;

    // get all nodes
    var allNodes = tree.nodes(root);

    var valueExtent = d3.extent(allNodes.map(valueFx));
    r.domain(valueExtent);

    start();
  }

  // Helpers
  // ----------------

  function collapse(d) {
    if (d.children) {
      d.all_children = d.children;
      d._children = d.children;
      d._children.forEach(collapse);
      d.children = null;
      d.hidden = true;
      d.completed = true;
    }
  }

  function worstPath(d) {
    var worst = undefined;
    if (d && d.children) {
      d.children.forEach(function (ch) {
        if (!worst) worst = ch;
        else if (valueFx(ch) < valueFx(worst)) worst = ch;
      });
      worst.all_children = worst._children;
      worst.children = worst._children;
      worst._children = null;
      if (worst.children) {
        worst.children.forEach(function (e) {
          e.hidden = false;
        });
      }

      worstPath(worst)
    }
  }

  function bestPath(d) {
    var best = undefined;
    if (d && d.children) {
      d.children.forEach(function (ch) {
        if (!best) best = ch;
        else if (valueFx(ch) > valueFx(best)) best = ch;
      });

      best.all_children = best._children;
      best.children = best._children;
      best._children = null;
      if (best.children) {
        best.children.forEach(function (e) {
          e.hidden = false;
        });
      }

      bestPath(best)
    }
  }

  function expandAll(d) {
    var children = (d.children)?d.children:d._children;
    if (d._children) {
      d.children = d._children;
      d.children.forEach(function (e){
          e.hidden = false;
      });
      d._children = null;
      d.hidden = false;
    }
    if(children)
      children.forEach(expandAll);
  }

  function updateOrderTree(key) {
    if (key === 'metric value') {
      tree = d3.layout.tree()
        .size([height, width]).sort(function (a, b) {
          if (valueFx(a) < valueFx(b)) return -1;
          if (valueFx(a) > valueFx(b)) return 1;
          return 0;
        });
    }
    else if (key === 'action_id') {
      tree = d3.layout.tree()
        .size([height, width]).sort(function (a, b) {
          if (idFx(a) < idFx(b)) return -1;
          if (idFx(a) > idFx(b)) return 1;
          return 0;
        });
    }
    else {
      tree = d3.layout.tree()
        .size([height, width]).sort(function (a, b) {
          if (codeFx(a) < codeFx(b)) return -1;
          if (codeFx(a) > codeFx(b)) return 1;
          return 0;
        });
    }
  }

  // Only show nodes completed (remove gray nodes)
  function showComplete(d) {
    if (valueFx(d) === 0){
      d.completed = false;
      d.hidden = true;
    }
    else{
      d.completed = true;
    }
    if (d.children) {
      d.children.forEach(showComplete);
    }
    else if (d._children){
      d._children.forEach(showComplete);
    }
  }

  function showIncomplete(d) {
    d.completed = true;
    d.hidden = false;

    if (d.children) {
      d.children.forEach(showIncomplete);
    }
    else if (d._children){
      d._children.forEach(showIncomplete);
    }
  }

  function drawTreeBackground(lineHeight){

    var labels = ['OVERALL', 'CONCEPTS', 'COMPETENCIES', 'PERFORMANCE MEASURES'];

    vis
      .selectAll('svg .tree-background')
      .selectAll('text').data(d3.range(MAX_DEPTH))
      .enter()
      .append('text')
      .text(function (d) {
        return labels[d];
      })
      .attr('x', function (d) {
        if (d == 0) {
            return d * depthWidth + depthWidth / 3;
        }
        else {
            return d * depthWidth + depthWidth / 8;
        }
      })
      .attr('y', function (d) {
        return 0;
      })
      .attr('class', 'group-container__title');

    vis
      .selectAll('svg .tree-background')
      .selectAll('line').data(d3.range(MAX_DEPTH))
      .enter()
      .append('line')
      .attr('x1', function (d) {
        if (d < 3) {
            return d * depthWidth + depthWidth / 1.3;
        }
        else {
            return d * depthWidth + depthWidth;
        }
      })
      .attr('x2', function (d) {
        if (d < 3) {
            return d * depthWidth + depthWidth / 1.3;
        }
        else {
            return d * depthWidth + depthWidth;
        }
      })
      .attr('y1', function (d) {
        return 0;
      })
      .attr('y2', function (d) {
        return lineHeight;
      })
      .attr("stroke-width", 2)
      .attr("stroke", "#EAEAEA");
  }

  function start() {
    vis.selectAll('div').remove();
    vis.selectAll('span').remove();
    vis.selectAll('select').remove();

    vis.insert('div', 'svg')
      .attr('class', 'group-container__title')
      .style('margin-left', '5px')
      .style('display', 'inline-block')
      .text('LOOK AT');

    vis.insert('div', 'svg')
      .attr('id', 'complete_pm')
      .attr('class', 'fr-btn fr-btn-default fr-btn-sm selected')
      .style('margin-left', '10px')
      .text('Addressed PMs')
      .on('click', function () {
        showComplete(root);
        update(root);

        //Toogle style of buttons
        d3.select(this)
          .attr('class', 'fr-btn fr-btn-default fr-btn-sm');

        vis.selectAll('#incomplete_pm')
          .attr('class', 'fr-btn fr-btn-underline fr-btn-sm');
      });

    vis.insert('div', 'svg')
      .attr('id', 'incomplete_pm')
      .attr('class', 'fr-btn fr-btn-underline fr-btn-sm')
      .style('margin-left', '10px')
      .text('All PMs')
      .on('click', function () {
        showIncomplete(root);
        update(root);

        //Toogle style of buttons
        d3.select(this)
          .attr('class', 'fr-btn fr-btn-default fr-btn-sm');

        vis.selectAll('#complete_pm')
          .attr('class', 'fr-btn fr-btn-underline fr-btn-sm');
      });

    vis.insert('div', 'svg')
      .attr('class', 'group-container__title')
      .style('margin-left', '45px')
      .style('display', 'inline-block')
      .text('SHOW');

    vis.insert('div', 'svg')
      .attr('class', 'fr-btn fr-btn-default fr-btn-sm')
      .style('margin-left', '10px')
      .text('Worst Path')
      .on('click', function () {
        expandAll(root);
        if(root.children){
          root.children.forEach(collapse);
          root.children.forEach(function (d) {
            d.hidden = false;
          });
        };
        worstPath(root);
        updateSVG();
        update(root);
      });

    vis.insert('div', 'svg')
      .attr('class', 'fr-btn fr-btn-default fr-btn-sm')
      .style('margin-left', '8px')
      .text('Best Path')
      .on('click', function () {
        expandAll(root);
        if(root.children){
          root.children.forEach(collapse);
          root.children.forEach(function (d) {
            d.hidden = false;
          });
        };

        bestPath(root);
        updateSVG();
        update(root);
      });

    vis.insert('div', 'svg')
      .attr('class', 'fr-btn fr-btn-default fr-btn-sm')
      .style('margin-left', '8px')
      .text('Expand All')
      .on('click', function () {
        expandAll(root);
        updateSVG();
        update(root);
      });

    vis.insert('div', 'svg')
      .attr('class', 'group-container__title')
      .style('margin-left', '45px')
      .style('display', 'inline-block')
      .text('SORTED BY');

    var dropdown = vis.insert('select', 'svg')
      .style('margin-left', '8px')
      .style('font-size', '13px')
      .on('change', function (value) {
        var selection = d3.select('select').node().value;
        updateOrderTree(selection);
        update(root);
      });

    dropdown.selectAll('option')
      .data(options)
      .enter()
      .append('option')
      .text(function (d) {
        return d.option;
      })
      .attr('value', function (d) {
        return d.key;
      });

    drawTreeBackground(height);

    root.all_children = root.children;
    root.children.forEach(collapse);
    root.children.forEach(function (d) {
      d.hidden = false;
      d.completed = true;
    });
    root.hidden = false;

    //By default show only completed PM
    root.completed = true;
    root.children.forEach(showComplete);

    //By default show the worst path
    worstPath(root);

    // draw tree
    update(root);
  }

  function updateSVG(){
    // compute the new height based on how many nodes are on the leaves
    var levelWidth = [1];
    var childCount = function(level, n) {
      if(n.children && n.children.length > 0) {
        if(levelWidth.length <= level + 1) levelWidth.push(0);
        levelWidth[level+1] += n.children.length;
        n.children.forEach(function(d) {
          childCount(level+1, d);
        });
      }
    };

    childCount(0, root);

    var newHeight;
    if (d3.max(levelWidth) > 5){
      newHeight = d3.max(levelWidth) * 60;
    }
    else{
      newHeight = height;
    }

    tree = tree.size([newHeight, width]);

    //Remove the existing svg element and reload it
    vis.select("svg").remove();
    d3.selectAll(".tooltip").remove();

    var svg = vis
      .append("svg")
      .attr("width", width + margin.left + margin.right)
      .attr("height", newHeight + margin.top + margin.bottom)
      .style("margin-top", '20px')
      .append("g")
      .attr('class', 'tree-container')
      .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

    vis.select('svg')
      .append("g")
      .attr('class', 'tree-background')
      .attr("transform", "translate(" + (margin.left - depthWidth / 2) + "," + margin.top + ")");

    drawTreeBackground(newHeight);
  }

  function update(source) {
    // Compute the new tree layout.
    var nodes = tree
      .nodes(root)
      .filter(function (e){
        return e.completed;
      })
      .filter(function (d) {
        return !d.hidden;
      })
      .reverse();

    var links = tree
      .links(nodes)
      .filter(function (e){
        return e.target.completed;
      });

    // Normalize for fixed-depth: d.y is actually for horizontal positioning
    nodes.forEach(function (d) {
      d.y = d.depth * depthWidth;
    });


    // Update the nodes…
    var svg = vis.selectAll('g.tree-container');

    var node = svg
      .selectAll("g.node")
      .data(nodes, function (d) {
        return d.id || (d.id = ++i);
      });

    // Enter any new nodes at the parent's previous position.
    var nodeEnter = node
      .enter()
      .append("g")
      .attr("class", "node")
      .attr("transform", function (d) {
        return "translate(" + source.y0 + "," + source.x0 + ")";
      });

    nodeEnter
      .append("circle")
      .attr("r", 0)
      .attr("data-tooltip-content", function (d){
        return d.label;
      })
      .on('click', onCircleClick);

    var maxRadius = r.range()[1];
    nodeEnter
      .append("text")
      .attr("id", "left_label")
      .attr("class", 'item-label js-selectable-item')
      .attr("x", function (d) {
        return -maxRadius;
      })
      .attr("text-anchor", function (d) {
        return "end";
      })
      .style("fill-opacity", 0)
      .on('click', onTextClick)
      .call(wrapText);

    nodeEnter
      .append("text")
      .attr("id", "right_label")
      .attr("class", 'item-label js-selectable-item')
      .attr("x", function (d) {
        return maxRadius;
      })
      .attr("text-anchor", function (d) {
        return "start";
      })
      .style("fill-opacity", 1)
      .on('click', onTextClick)
      .call(wrapText2);

    // update node active class without transition
    svg.selectAll("g.node")
        .classed('active', isSelected);

    // Transition nodes to their new position.
    var nodeUpdate = node.transition()
        .duration(duration)
        .attr("transform", function (d) {
          return "translate(" + d.y + "," + d.x + ")";
        });

    nodeUpdate
      .select("circle")
      .attr("r", radius)
      .style("fill", fillColor)
      .style("stroke", strokeColor);

    nodeUpdate
      .select(".item-label")
      .style("fill-opacity", 1);

    // Transition exiting nodes to the parent's new position.
    var nodeExit = node
      .exit()
      .transition()
      .duration(duration)
      .attr("transform", function (d) {
        return "translate(" + source.y + "," + source.x + ")";
      })
      .remove();

    nodeExit.select("circle")
      .attr("r", 1e-6);

    nodeExit.select("text")
      .style("fill-opacity", 1e-6);

    // Update the links…
    var link = svg.selectAll("path.link")
      .data(links, function (d) {
        return d.target.id;
      });

    // Enter any new links at the parent's previous position.
    link
      .enter()
      .insert("path", "g")
      .attr("class", "link")
      .attr("d", function (d) {
          var o = {x: source.x0, y: source.y0};
          return diagonal({source: o, target: o});
      });

    // Transition links to their new position.
    link
      .transition()
      .duration(duration)
      .attr("d", diagonal);

    // Transition exiting nodes to the parent's new position.
    link
      .exit()
      .transition()
      .duration(duration)
      .attr("d", function (d) {
          var o = {x: source.x, y: source.y};
          return diagonal({source: o, target: o});
      })
      .remove();

    // Stash the old positions for transition.
    nodes.forEach(function (d) {
      d.x0 = d.x;
      d.y0 = d.y;
    });
  }

  // Toggle selection
  function onCircleClick(d) {
    if (d.children) {
        d._children = d.children;
        d.children = null;
        if (d._children) {
            d._children.forEach(function (n) {
                n.hidden = true;
            });
        }
    } else {
        d.children = d._children;
        d._children = null;
        if (d.children) {
            d.children.forEach(function (n) {
                n.hidden = false;
            });
        }
    }
    updateSVG();
    update(d);
  }

  // Toggle expand/collapse
  function onTextClick(d) {
    selectionChangedCallback([d]);
  }

  function createLabel(d) {
  //    return (d.children ? '[-] ' : d._children ? '[+] ': '') + d.label;
      return d.label;
  }

  function wrapText(textElements) {
    textElements.each(function (d) {
      var
        text = d3.select(this),
        width = 150,
        label = createLabel(d),
        words = label.split(/\s+/).reverse(),
        word,
        line = [],
        lineNumber = 0,
        lineHeight = 10, //px
        x = text.attr("x"),
        y = text.attr("y"),
        textAnchor = text.attr("text-anchor");

      var addSpan = function (value, lineNumber) {
        return text.append("tspan")
          .attr("x", x)
          .attr("dy", lineNumber > 0 ? lineHeight : 0)
          .attr('text-anchor', textAnchor)
          .text(value);
      };

      // clear text
      text.text(null);

      var tspan = addSpan(null, ++lineNumber);
      // start adding lines (tspans)
      while (word = words.pop()) {
        line.push(word);
        tspan.text(line.join(" "));
        if (tspan.node().getComputedTextLength() > width) {
          line.pop();
          tspan.text(line.join(" "));
          line = [word];
          tspan = addSpan(word, ++lineNumber);
        }
      }
      text.attr('y', -lineHeight / 2 * lineNumber);
    });
  }

  function wrapText2(textElements) {
    textElements.each(function (d) {
      var
        text = d3.select(this),
        width = 60,
        line = [],
        lineNumber = 0,
        lineHeight = 10, //px
        x = text.attr("x"),
        y = text.attr("y"),
        textAnchor = text.attr("text-anchor");

      var addSpan = function (value, lineNumber) {
        return text.append("tspan")
          .attr("x", x)
          .attr("dy", lineNumber > 0 ? lineHeight : 5)
          .attr('text-anchor', textAnchor)
          .text(value);
      };

      // clear text
      text.text(null);

      // add expand/collapse and value of the node
      addSpan(pctFormatter(d.value), lineNumber).classed('item-value', true);

      text.attr('y', -lineHeight / 2 * lineNumber);
    });
  }

  function _updateSelections() {
    vis
      .selectAll('g.tree-container')
      .selectAll("g.node")
      .classed('active', isSelected);
  }

  // Check if `d` is selected.
  function isSelected(d) {
    return currentSelections.find(function(s) {
      return s.id == d.id;
    });
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
  chart.updateSelections = function() {
    _updateSelections();
  };


  // Return the public attributes and methods
  return chart;
}