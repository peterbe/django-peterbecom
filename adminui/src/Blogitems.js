import React from 'react';
import { Link } from 'react-router-dom';
import {
  Container,
  Loader,
  Table,
  Button,
  Label,
  Input
} from 'semantic-ui-react';
import { debounce } from 'throttle-debounce';
import { DisplayDate, ShowServerError } from './Common';

class Blogitems extends React.Component {
  state = {
    blogitems: null,
    count: 0,
    page: 1,
    serverError: null,
    search: '',
    orderBy: null
  };
  componentDidMount() {
    this.fetchBlogitems();
  }

  fetchBlogitems = async () => {
    const { accessToken } = this.props;
    if (!accessToken) {
      throw new Error('No accessToken');
    }
    const { page, search } = this.state;
    let url = `/api/v0/plog/?page=${page}&search=${encodeURIComponent(search)}`;
    if (this.state.orderBy) {
      url += `&order=${encodeURIComponent(this.state.orderBy)}`;
    }
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${accessToken}`
      }
    });
    if (response.ok) {
      const data = await response.json();
      this.setState({ blogitems: data.blogitems, count: data.count });
    } else {
      this.setState({ serverError: response });
    }
  };

  changeOrderColumn = () => {
    this.setState(
      {
        orderBy: this.state.orderBy === 'pub_date' ? 'modify_date' : 'pub_date'
      },
      () => this.fetchBlogitems()
    );
  };

  getOrderLabel = () => {
    return this.state.orderBy === 'pub_date' ? 'Published' : 'Modified';
  };

  getOrderDirection = () => {
    if (this.state.orderBy) {
      return this.state.orderBy.charAt(0) === '-' ? 'descending' : 'ascending';
    }
    return 'ascending';
  };

  render() {
    return (
      <Container>
        <ShowServerError error={this.state.serverError} />
        {this.state.blogitems === null && this.state.serverError === null ? (
          <Loader
            active
            size="massive"
            inline="centered"
            content="Loading Blogitems..."
            style={{ margin: '200px 0' }}
          />
        ) : null}
        {this.state.blogitems && (
          <BlogitemsTable
            blogitems={this.state.blogitems}
            count={this.state.count}
            orderLabel={this.getOrderLabel()}
            orderDirection={this.getOrderDirection()}
            changeOrderColumn={this.changeOrderColumn}
            updateFilterSearch={search => {
              this.setState({ search }, this.fetchBlogitems);
            }}
          />
        )}
      </Container>
    );
  }
}

export default Blogitems;

class BlogitemsTable extends React.PureComponent {
  state = {
    search: ''
  };

  render() {
    const { blogitems, count } = this.props;
    return (
      <Table celled>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>Title ({count})</Table.HeaderCell>
            <Table.HeaderCell
              sorted={this.props.orderDirection}
              onClick={event => {
                this.props.changeOrderColumn();
              }}
            >
              {this.props.orderLabel}
            </Table.HeaderCell>
          </Table.Row>
          <Table.Row>
            <Table.HeaderCell colSpan={2}>
              <Input
                icon="search"
                placeholder="Search..."
                style={{ width: '90%' }}
                list="search-autofills"
                value={this.state.search}
                onChange={event => {
                  this.setState(
                    { search: event.target.value },
                    debounce(500, () => {
                      this.props.updateFilterSearch(this.state.search);
                    })
                  );
                }}
              />
              {this.state.search ? (
                <Button
                  icon="remove"
                  onClick={event => {
                    this.setState({ search: '' }, () => {
                      this.props.updateFilterSearch('');
                    });
                  }}
                />
              ) : null}
            </Table.HeaderCell>
          </Table.Row>
        </Table.Header>

        <Table.Body>
          {blogitems.map(item => {
            return (
              <Table.Row key={item.oid}>
                <Table.Cell>
                  <Link to={`/plog/${item.oid}`}>{item.title}</Link>
                  {item.categories.map(category => (
                    <Label
                      key={category.id}
                      size="tiny"
                      style={{ cursor: 'pointer' }}
                      onClick={event => {
                        this.updateFilterCategories(category.name);
                      }}
                    >
                      {category.name}
                    </Label>
                  ))}

                  {!item._is_published ? (
                    <Label size="tiny" color="orange">
                      Published <DisplayDate date={item.pub_date} />
                    </Label>
                  ) : null}

                  {!item.summary && (
                    <Label circular empty color="brown" title="No summary!" />
                  )}
                </Table.Cell>
                <Table.Cell>
                  <DisplayDate date={item.modify_date} />
                </Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>
      </Table>
    );
  }
}
