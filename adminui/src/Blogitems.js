import React from 'react';
import { observer } from 'mobx-react';
import { Link } from 'react-router-dom';
import {
  Button,
  Container,
  Loader,
  Label,
  Table,
  Input,
  Pagination,
  Message
} from 'semantic-ui-react';
import { DisplayDate, Breadcrumbs } from './Common';
import store from './Store';

export default observer(
  class Blogitems extends React.Component {
    componentDidMount() {
      document.title = 'Blogitems';
      if (
        store.blogitems.blogitems.size &&
        store.blogitems.latestBlogitemDate
      ) {
        store.blogitems.updateBlogitems();
      } else {
        store.blogitems.fetchBlogitems();
      }
    }
    render() {
      return (
        <Container>
          <Breadcrumbs active="Blogitems" />
          {store.blogitems.serverError ? (
            <Message negative>
              <Message.Header>Server Error</Message.Header>
              <p>
                <code>{store.blogitems.serverError}</code>
              </p>
              <Button
                onClick={event => {
                  store.blogitems.fetchBlogitems();
                }}
              >
                Reload
              </Button>
            </Message>
          ) : null}
          {!store.blogitems.loaded ? <Loader active inline="centered" /> : null}
          {store.blogitems.loaded && !store.blogitems.serverError ? (
            <div>
              <BlogitemsTable items={store.blogitems.pageFiltered} />
              <Pagination
                defaultActivePage={store.blogitems.activePage}
                totalPages={Math.ceil(
                  store.blogitems.filteredCount / store.blogitems.pageBatchSize
                )}
                onPageChange={(event, data) => {
                  store.blogitems.setActivePage(data.activePage);
                }}
              />
            </div>
          ) : null}
        </Container>
      );
    }
  }
);

class BlogitemsTable extends React.PureComponent {
  state = {
    search: ''
  };
  updateFilterSearch = event => {
    this.setState({ search: event.target.value }, () => {
      const filters = store.blogitems.filters;
      filters.search = this.state.search;
      store.blogitems.setFilters(filters);
    });
  };

  updateFilterCategories = category => {
    const filters = store.blogitems.filters;
    if (!filters.categories.remove(category)) {
      filters.categories.push(category);
    }
    store.blogitems.setFilters(filters);
  };

  render() {
    const { items } = this.props;
    // const items = store.filteredBlogitems();
    return (
      <Table celled>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>Title</Table.HeaderCell>
            <Table.HeaderCell>Modified</Table.HeaderCell>
          </Table.Row>
          <Table.Row>
            <Table.HeaderCell colSpan={2}>
              <Input
                icon="search"
                placeholder="Search..."
                value={this.state.search}
                onChange={this.updateFilterSearch}
              />
              {store.blogitems.filters.categories.map(category => (
                <Label
                  key={category}
                  size="tiny"
                  color="green"
                  style={{ cursor: 'pointer' }}
                  onClick={event => {
                    this.updateFilterCategories(category);
                  }}
                >
                  {category}
                </Label>
              ))}
              {store.blogitems.filters.categories.length ||
              store.blogitems.filters.search ? (
                <Button
                  icon="remove"
                  onClick={event => {
                    this.setState({ search: '' });
                    store.blogitems.resetFilters();
                  }}
                />
              ) : null}
            </Table.HeaderCell>
          </Table.Row>
        </Table.Header>

        <Table.Body>
          {items.map(item => {
            return (
              <Table.Row key={item.oid}>
                <Table.Cell>
                  <Link to={`/blogitems/${item.id}`}>{item.title}</Link>
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
                </Table.Cell>
                <Table.Cell>
                  <DisplayDate date={item.modify_date} />
                </Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>

        {/* <Table.Footer>
          <Table.Row>
            <Table.HeaderCell colSpan="3">
              <Menu floated="right" pagination>
                <Menu.Item as="a" icon>
                  <Icon name="chevron left" />
                </Menu.Item>
                <Menu.Item as="a">1</Menu.Item>
                <Menu.Item as="a">2</Menu.Item>
                <Menu.Item as="a">3</Menu.Item>
                <Menu.Item as="a">4</Menu.Item>
                <Menu.Item as="a" icon>
                  <Icon name="chevron right" />
                </Menu.Item>
              </Menu>
            </Table.HeaderCell>
          </Table.Row>
        </Table.Footer> */}
      </Table>
    );
  }
}
