/** @jsx React.DOM */

var TBody = React.createClass({
  getInitialState: function(){
     return {
       items: []
     }
  },
  componentDidMount: function() {
    fetch('/ajaxornot/view3-data')
      .then(function(response) {
        return response.json();
      }).then(function(body) {
        // document.body.innerHTML = body
        // console.log(body);
        this.setState({items: body.items})
      }.bind(this))
  },
  renderRow: function(item) {
    return <tr>
      <td>{item.title}</td>
    </tr>
  },
  render: function() {
    var items = this.state.items;
    // console.log(items);
    // return <tr><td>one</td></tr>
    return <tbody>{items.map(this.renderRow.bind(this))}</tbody>
  }
});

React.render(<TBody/>, document.getElementById('tbody'));
