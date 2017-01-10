
// "this": corresponds to the HTML container element (eg. div.slice-body__visualization)
var container = d3.select(this);
var dataItems = data.items[0];

// IMPORTANT: max depth is not dynamic, set it here
var MAX_DEPTH = 4;




// the code below is modified from https://bl.ocks.org/mbostock/4339083

var margin = {top: 20, right: 120, bottom: 20, left: 120},
  width = 960 - margin.right - margin.left,
  height = 800 - margin.top - margin.bottom;
var depthWidth = width / MAX_DEPTH;

var pctFormatter = d3.format(',.0%');

var i = 0,
  duration = 750,
  root;

var tree = d3.layout.tree()
  .size([height, width]);

var diagonal = d3.svg.diagonal()
  .projection(function(d) { return [d.y, d.x]; });

var svgEnter = container.selectAll('svg').data([{}])
  .enter()
  .append("svg")
  .attr("width", width + margin.right + margin.left)
  .attr("height", height + margin.top + margin.bottom)

// background gridlines
svgEnter
  .append("g")
  .attr('class', 'tree-background')
  .attr("transform", "translate(" + (margin.left  - depthWidth/2)+ "," + margin.top + ")");

// tree container
svgEnter
  .append("g")
  .attr('class', 'tree-container')
  .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

var svg = container.selectAll('g.tree-container');


root = dataItems;
root.x0 = height / 2;
root.y0 = 0;

function collapse(d) {
  if (d.children) {
    d._children = d.children;
    d._children.forEach(collapse);
    d.children = null;
  }
}



// get all nodes
var allNodes = tree.nodes(root);

var valueFx = function(d) { return d.value; };
var valueExtent = d3.extent(allNodes.map(valueFx));

// < 70% = red
// 70 to < 80% = light red (with red outline)
// 80% to < 90% = white (with black outline)
// 90% or more = green
// no score = gray (with dark gray outline)

var domainValues = [0, 0.0000000001, 0.7000, 0.8000, 0.9000, 1];
var c1 = d3.scale.quantile()
    .domain(domainValues)
    .range(['#ccc', '#cb181d', '#cb181d', '#fc9272', '#fff', '#006d2c']),
  fillColor = function(d) {return c1(valueFx(d));},
  c2 = d3.scale.quantile()
    .domain(domainValues)
    .range(['#666', '#cb181d', '#cb181d', '#cb181d', '#000', '#006d2c']),
  strokeColor = function(d) { return c2(valueFx(d));},

  r = d3.scale.linear()
    .domain(valueExtent)
    .range([5, 20]),
  radius = function(d) { return 15/*r(valueFx(d))*/;}
  ;


function start() {
  container.selectAll('svg .tree-background')
    .selectAll('line').data(d3.range(MAX_DEPTH))
    .enter()
    .append('line')
      .attr('x1', function (d) { console.log(d); return d * depthWidth; })
      .attr('x2', function (d) { return d * depthWidth; })
      .attr('y1', function (d) { return 0; })
      .attr('y2', function (d) { return height; })
      .attr("stroke-width", 2)
      .attr("stroke", "#EAEAEA");


  // expand only the first level on nodes
  root.children.forEach(collapse);

  // expand selected items
  var selectedItems = allNodes.filter(function(d){ return d._selected;});
  selectedItems.forEach(function(d){
    var p = d.parent;
    while(p) {
      if (!p.children) {
        p.children = p._children;
        p._children = null;
      }
      p = p.parent;
    }
  });

  // draw tree
  update(root);

}



function update(source) {

  // Compute the new tree layout.
  var nodes = tree.nodes(root).reverse(),
    links = tree.links(nodes);

  // Normalize for fixed-depth: d.y is actually for horizontal positioning
  nodes.forEach(function(d) { d.y = d.depth * depthWidth; });


  // Update the nodes…
  var node = svg.selectAll("g.node")
    .data(nodes, function(d) { return d.id || (d.id = ++i); });

  // Enter any new nodes at the parent's previous position.
  var nodeEnter = node.enter().append("g")
      .attr("class", "node")
      .attr("transform", function(d) { return "translate(" + source.y0 + "," + source.x0 + ")"; })
    ;

  nodeEnter.append("circle")
    .attr("r", 0)
    .attr("class", 'js-selectable-item')
    .on('click', onCircleClick);

  var maxRadius = r.range()[1];
  nodeEnter.append("text")
    .attr("class", 'item-label')
    .attr("x", function(d) { return d.children || d._children ? -maxRadius : maxRadius; })
    .attr("text-anchor", function(d) { return d.children || d._children ? "end" : "start"; })
    .style("fill-opacity", 0)
    .on('click', onTextClick)
    .call(wrapText)
  ;

  // update node active class without transition
  svg.selectAll("g.node")
    .classed('active', function(d) {return d._selected; })
  ;
  // Transition nodes to their new position.
  var nodeUpdate = node.transition()
      .duration(duration)
      .attr("transform", function(d) { return "translate(" + d.y + "," + d.x + ")"; })
    ;

  nodeUpdate.select("circle")
    .attr("r", radius)
    .style("fill", fillColor)
    .style("stroke", strokeColor)
  ;

  nodeUpdate.select(".item-label")
    .style("fill-opacity", 1)
  ;

  // Transition exiting nodes to the parent's new position.
  var nodeExit = node.exit().transition()
    .duration(duration)
    .attr("transform", function(d) { return "translate(" + source.y + "," + source.x + ")"; })
    .remove();

  nodeExit.select("circle")
    .attr("r", 1e-6);

  nodeExit.select("text")
    .style("fill-opacity", 1e-6);

  // Update the links…
  var link = svg.selectAll("path.link")
    .data(links, function(d) { return d.target.id; });

  // Enter any new links at the parent's previous position.
  link.enter().insert("path", "g")
    .attr("class", "link")
    .attr("d", function(d) {
      var o = {x: source.x0, y: source.y0};
      return diagonal({source: o, target: o});
    });

  // Transition links to their new position.
  link.transition()
    .duration(duration)
    .attr("d", diagonal);

  // Transition exiting nodes to the parent's new position.
  link.exit().transition()
    .duration(duration)
    .attr("d", function(d) {
      var o = {x: source.x, y: source.y};
      return diagonal({source: o, target: o});
    })
    .remove();

  // Stash the old positions for transition.
  nodes.forEach(function(d) {
    d.x0 = d.x;
    d.y0 = d.y;
  });
}


// toggle selection
function onCircleClick(d) {
  var isSelected = d._selected;
  container.selectAll('.active')
    .classed('active', false)
    .each(function(item){
      item._selected = false;
    })
  ;

  d._selected = !isSelected;
  d3.select(this.parentNode).classed('active', d._selected);

  // expand if the item got selected
  if (d._selected && !d.children) {
    d.children = d._children;
    d._children = null;
    update(d);
  }
}

// toggle expand/collapse
function onTextClick(d) {
  if (d.children) {
    d._children = d.children;
    d.children = null;
  } else {
    d.children = d._children;
    d._children = null;
  }

  // expand/collapse children
  update(d);
  // change icon
  wrapText(d3.select(this))
}


function createLabel(d) {
  // return (d.children ? '[-] ' : d._children ? '[+] ': '') + pctFormatter(d.value) + ' ' + d.label ;//(d.children ? ' [-]' : d._children ? ' [+]': '') + ' ' +
  return d.label ;//(d.children ? ' [-]' : d._children ? ' [+]': '') + ' ' +
}


function wrapText(textElements) {
  textElements.each(function(d) {
    var
      text = d3.select(this),
      width = 120,
      label = createLabel(d),
      words = label.split(/\s+/).reverse(),
      word,
      line = [],
      lineNumber = 0,
      lineHeight = 10, //px
      x = text.attr("x"),
      y = text.attr("y"),
      textAnchor = text.attr("text-anchor")
      ;

    var addSpan = function(value, lineNumber) {
      return text.append("tspan")
        .attr("x", x)
        .attr("dy", lineNumber > 0 ? lineHeight : 0)
        .attr('text-anchor', textAnchor)
        .text(value)
        ;
    };

    // clear text
    text.text(null);
    // add expand/collapse and value of the node
    addSpan((d.children ? '[-] ' : d._children ? '[+] ': '') + pctFormatter(d.value), lineNumber)
      .classed('item-value', true)
    ;


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
    text.attr('y',  - lineHeight/2 * lineNumber );
  });
}

start();