/* To generate `view6.js` got to the directory where `views6.jsx` is
   and run `jsx view6.jsx > view6.js`
*/
var Row = React.createClass({
  render: function() {
    var item = this.props.item;
    return <tr>
      <td>
        <a href={'/plog/' + item.slug}>{item.title}</a>
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
