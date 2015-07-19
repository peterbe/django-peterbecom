/* To generate `view6.js` got to the directory where `views6.jsx` is
   and run `jsx view6.jsx > view6.js`
*/
var Row = React.createClass({displayName: "Row",
  render: function() {
    var item = this.props.item;
    return React.createElement("tr", null, 
      React.createElement("td", null, 
        React.createElement("a", {href: '/plog/' + item.slug}, item.title)
      ), 
      React.createElement("td", null, item.pub_date), 
      React.createElement("td", null, 
      
        item.categories.map(function(category) {
          return React.createElement("a", {href: '/oc-' + category.replace(' ', '+'), 
            className: "label label-default"}, category)
        })
      
      ), 
      React.createElement("td", null, 
      
        item.keywords.map(function(keyword) {
          return React.createElement("span", {className: "label label-default"}, keyword)
        })
      
      )
    )
  }
});

var Table = React.createClass({displayName: "Table",
  getInitialState: function(){
     return {
       items: []
     }
  },
  componentDidMount: function() {
    fetch('/ajaxornot/view6-data')
      .then(function(response) {
        return response.json();
      }).then(function(body) {
        this.setState({items: body.items})
      }.bind(this))
  },
  render: function() {
    var rows = [];
    this.state.items.forEach(function(item) {
      rows.push(React.createElement(Row, {key: item.slug, item: item}));
    });

    return React.createElement("table", {className: "table table-condensed"}, 
      React.createElement("thead", null, 
        React.createElement("tr", null, 
          React.createElement("th", null, "Title"), 
          React.createElement("th", {className: "pub-date"}, "Publish Date"), 
          React.createElement("th", null, "Categories"), 
          React.createElement("th", null, "Keywords")
        )
      ), 
      React.createElement("tbody", null, rows)
    )
  }
});

React.render(React.createElement(Table, null), document.getElementById('table'));
