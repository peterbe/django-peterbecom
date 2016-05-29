/* To generate `view7b.js` got to the directory where `views7b.jsx` is
   and run `jsx view7b.jsx > view7b.js`
*/
var Row = React.createClass({displayName: "Row",
  handleTitleClick: function(e) {
    e.preventDefault();
    if (confirm(e.target.textContent)) {
      window.location.href = e.target.href;
    }
  },
  render: function() {
    var item = this.props.item;
    return React.createElement("tr", null, 
      React.createElement("td", null, 
        React.createElement("a", {href: '/plog/' + item.slug, 
            onClick: this.handleTitleClick.bind(item)}, item.title)
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
  getPostsFromLocalStorage: function() {
    return JSON.parse(localStorage.getItem('posts') || '[]');
  },
  setPostsFromLocalStorage: function(posts) {
    localStorage.setItem('posts', JSON.stringify(posts));
  },
  componentDidMount: function() {
    var t0 = performance.now();
    var items = this.getPostsFromLocalStorage();
    var t1 = performance.now();
    console.log(items.length, 'records extracted');
    console.log((t1 - t0).toFixed(2) + 'ms to extract');
    this.setState({items: items});
    if (!items.length) {
      t0 = performance.now();
      fetch('/ajaxornot/view6-data')
        .then(function(response) {
          return response.json();
        }).then(function(body) {
          t1 = performance.now();
          console.log((t1 - t0).toFixed(2), 'ms to fetch remotely');
          this.setPostsFromLocalStorage(body.items);
          alert("You can refresh the page now");
        }.bind(this));
    }
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
