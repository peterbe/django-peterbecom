/* To generate `view7.js` got to the directory where `views7.jsx` is
   and run `jsx view7.jsx > view7.js`

   Note: This file is very much just copied from view6.jsx and modified.
*/

// Set up the schema builder for lovefield
var schemaBuilder = lf.schema.create('blogposts', 1);
schemaBuilder.createTable('post')
  .addColumn('title', lf.Type.STRING)
  .addColumn('slug', lf.Type.STRING)
  .addColumn('pub_date', lf.Type.STRING)
  .addColumn('keywords', lf.Type.STRING)
  .addColumn('categories', lf.Type.STRING)
  .addPrimaryKey(['slug'])
;

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
  fetch: function() {
    return fetch('/ajaxornot/view6-data')
      .then(function(response) {
        return response.json();
      }).then(function(body) {
        schemaBuilder.connect().then(function(db) {
          var table = db.getSchema().table('post');
          var rows = [];
          body.items.forEach(function(item) {
            rows.push(table.createRow({
              slug: item.slug,
              title: item.title,
              pub_date: item.pub_date,
              keywords: item.keywords,
              categories: item.categories,
            }));
          });
          return db.insertOrReplace().into(table).values(rows).exec();
        });
      });
  },
  getPostsFromDB: function() {
    return schemaBuilder.connect().then(function(db) {
      var table = db.getSchema().table('post');
      return db.select().from(table).exec();
    });
    // }).then(function(results) {
    //   return results;
    // });
  },
  componentDidMount: function() {
    var t0 = performance.now();
    this.getPostsFromDB()
    .then(function(results) {
      var t1 = performance.now();
      console.log(results.length, 'records extracted');
      console.log((t1 - t0).toFixed(2) + 'ms to extract');
      this.setState({items: results});
      if (!results.length) {
        t0 = performance.now()
        this.fetch().then(function() {
          t1 = performance.now();
          console.log((t1 - t0).toFixed(2) + 'ms to fetch');
          alert("You can refresh the page now");
        }.bind(this));
      }
    }.bind(this));
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
