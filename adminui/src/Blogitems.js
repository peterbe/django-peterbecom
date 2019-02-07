import React from 'react';
import { Link } from 'react-router-dom';
import {
  Button,
  Container,
  Input,
  Label,
  Loader,
  Table
} from 'semantic-ui-react';
import { debounce } from 'throttle-debounce';
import { DisplayDate, ShowServerError } from './Common';

function getDefaultSearch() {
  if (window.location && window.location.search) {
    const searchParams = new URLSearchParams(
      window.location.search.slice(1, window.location.search.length)
    );
    return searchParams.get('search') || '';
  }
  return '';
}

class Blogitems extends React.Component {
  state = {
    blogitems: null,
    count: 0,
    orderBy: null,
    page: 1,
    search: getDefaultSearch(),
    serverError: null
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
            content="Loading Blogitems..."
            inline="centered"
            size="massive"
            style={{ margin: '200px 0' }}
          />
        ) : null}
        {this.state.blogitems && (
          <BlogitemsTable
            blogitems={this.state.blogitems}
            changeOrderColumn={this.changeOrderColumn}
            count={this.state.count}
            orderDirection={this.getOrderDirection()}
            orderLabel={this.getOrderLabel()}
            search={this.state.search}
            updateFilterSearch={search => {
              this.setState({ search }, () => {
                this.props.history.push({
                  search: `?search=${encodeURIComponent(this.state.search)}`
                });
                this.fetchBlogitems();
              });
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
    search: this.props.search
  };

  render() {
    const { blogitems, count } = this.props;
    return (
      <Table celled>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>
              Title ({count.toLocaleString()})
            </Table.HeaderCell>
            <Table.HeaderCell
              onClick={event => {
                this.props.changeOrderColumn();
              }}
              sorted={this.props.orderDirection}
            >
              {this.props.orderLabel}
            </Table.HeaderCell>
          </Table.Row>
          <Table.Row>
            <Table.HeaderCell colSpan={2}>
              <Input
                icon="search"
                list="search-autofills"
                onChange={event => {
                  this.setState(
                    { search: event.target.value },
                    debounce(500, () => {
                      this.props.updateFilterSearch(this.state.search);
                    })
                  );
                }}
                placeholder="Search..."
                style={{ width: '90%' }}
                value={this.state.search}
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
                      onClick={event => {
                        this.updateFilterCategories(category.name);
                      }}
                      size="tiny"
                      style={{ cursor: 'pointer' }}
                    >
                      {category.name}
                    </Label>
                  ))}

                  {!item._is_published ? (
                    <Label color="orange" size="tiny">
                      Published <DisplayDate date={item.pub_date} />
                    </Label>
                  ) : null}

                  {!item.summary && (
                    <Label circular color="brown" empty title="No summary!" />
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
