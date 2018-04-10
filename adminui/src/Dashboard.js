import React from 'react';
import { observer } from 'mobx-react';
import { Header } from 'semantic-ui-react';
import { Link } from 'react-router-dom';
import {
  Button,
  Dimmer,
  Container,
  Loader,
  Label,
  Table,
  Input,
  Pagination,
} from 'semantic-ui-react';
import { DisplayDate } from './Common';
import store from './Store';

export default observer(
  class Dashboard extends React.Component {
    componentDidMount() {
      if (store.blogitems.size && store.latestBlogitemDate) {
        store.updateBlogitems();
      } else {
        store.fetchBlogitems();
      }
    }
    render() {
      // console.log(store.filtered, store.filteredCount);
      // return <h2>Hi!</h2>;
      // let items;
      // if (store.blogitems.size) {
      //   items = store.pageFiltered;
      //   console.log(items.size);
      //   // filteredCount = store.filteredCount;
      // }
      return (
        <Container>
          <Header as="h1">Dashboard</Header>
          {/* <Breadcrumb>
            <Breadcrumb.Section link>Home</Breadcrumb.Section>
            <Breadcrumb.Divider icon='right chevron' />
            <Breadcrumb.Section link>Registration</Breadcrumb.Section>
            <Breadcrumb.Divider icon='right arrow' />
            <Breadcrumb.Section active>Personal Information</Breadcrumb.Section>
          </Breadcrumb> */}
          {!store.blogitems.size ? (
            <Dimmer active inverted>
              <Loader size="massive">Loading</Loader>
            </Dimmer>
          ) : (
            <div>
              <BlogitemsTable items={store.pageFiltered} />
              <Pagination
                defaultActivePage={store.activePage}
                totalPages={Math.ceil(
                  store.filteredCount / store.pageBatchSize
                )}
                onPageChange={(event, data) => {
                  store.setActivePage(data.activePage);
                }}
              />
            </div>
          )}
        </Container>
      );
    }
  }
);

class BlogitemsTable extends React.PureComponent {
  state = {
    search: '',
  };
  updateFilterSearch = event => {
    this.setState({ search: event.target.value }, () => {
      const filters = store.filters;
      filters.search = this.state.search;
      store.setFilters(filters);
    });
  };

  updateFilterCategories = category => {
    const filters = store.filters;
    if (!filters.categories.remove(category)) {
      filters.categories.push(category);
    }
    store.setFilters(filters);
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
              {store.filters.categories.map(category => (
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
              {store.filters.categories.length || store.filters.search ? (
                <Button
                  icon="trash"
                  onClick={event => {
                    this.setState({ search: '' });
                    store.resetFilters();
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
                  <Link to={`/blogitem/${item.id}`}>{item.title}</Link>
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
