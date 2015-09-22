/* To generate `view7b.js` got to the directory where `views7b.jsx` is
   and run `jsx view7b.jsx > view7b.js`
*/
var Row = React.createClass({
  handleTitleClick: function(e) {
    e.preventDefault();
    if (confirm(e.target.textContent)) {
      window.location.href = e.target.href;
    }
  },
  render: function() {
    var item = this.props.item;
    return <tr>
      <td>
        <a href={'/plog/' + item.slug}
            onClick={this.handleTitleClick.bind(item)}>{item.title}</a>
      </td>
      <td>{item.pub_date}</td>
      <td>
      {
        item.categories.map(function(category) {
          return <a href={'/oc-' + category.replace(' ', '+')}
              className="label label-default">{category}</a>
        })
      }
      </td>
      <td>
      {
        item.keywords.map(function(keyword) {
          return <span className="label label-default">{keyword}</span>
        })
      }
      </td>
    </tr>
  }
});

var Table = React.createClass({
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
      rows.push(<Row key={item.slug} item={item}/>);
    });

    return <table className="table table-condensed">
      <thead>
        <tr>
          <th>Title</th>
          <th className="pub-date">Publish Date</th>
          <th>Categories</th>
          <th>Keywords</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  }
});

React.render(<Table/>, document.getElementById('table'));
