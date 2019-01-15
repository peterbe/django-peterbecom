import React from 'react';
import { Header, Container, Loader, Table } from 'semantic-ui-react';

import { filterToQueryString, ShowServerError } from './Common';
import { BASE_URL } from './Config';

class BlogitemHits extends React.Component {
  state = {
    ongoing: null,
    loading: true,
    serverError: null,
    hits: null,
    categories: null,
    summedCategoryScores: null,
    filters: null
  };

  componentDidMount() {
    document.title = 'Blogitem Hits';
    this.fetchHits();
  }

  fetchHits = async () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    let response;
    let url = '/api/v0/plog/hits/';
    if (this.state.filters) {
      url += `?${filterToQueryString(this.state.filters)}`;
    }
    try {
      response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
    } catch (ex) {
      return this.setState({ serverError: ex });
    }

    if (this.dismounted) {
      return;
    }
    if (response.ok) {
      const data = await response.json();
      this.setState({
        loading: false,
        hits: data.all_hits,
        categories: data.categories,
        summedCategoryScores: data.summed_category_scores,
        serverError: null
      });
    } else {
      this.setState({ serverError: response });
    }
  };

  render() {
    const {
      loading,
      serverError,
      hits,
      categories,
      summedCategoryScores
    } = this.state;

    return (
      <Container textAlign="center">
        <Header as="h1">Blogitem Hits</Header>
        <ShowServerError error={this.state.serverError} />
        {!serverError && loading && (
          <Container>
            <Loader
              active
              size="massive"
              inline="centered"
              content="Loading..."
              style={{ margin: '200px 0' }}
            />
          </Container>
        )}

        {hits && <Hits hits={hits} categories={categories} />}
        {summedCategoryScores && (
          <Categories summedCategoryScores={summedCategoryScores} />
        )}
      </Container>
    );
  }
}

export default BlogitemHits;

class Hits extends React.PureComponent {
  render() {
    const { categories, hits } = this.props;

    return (
      <Table celled className="hits">
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>Title</Table.HeaderCell>
            <Table.HeaderCell>Score</Table.HeaderCell>
            <Table.HeaderCell>Hits</Table.HeaderCell>
            <Table.HeaderCell>Age (days)</Table.HeaderCell>
          </Table.Row>
        </Table.Header>

        <Table.Body>
          {hits.map(record => {
            const theseCategories = categories[record.id] || [];
            return (
              <Table.Row key={record.id}>
                <Table.Cell>
                  <a
                    href={BASE_URL + record._absolute_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {record.title}
                  </a>{' '}
                  {theseCategories.map(name => {
                    return (
                      <a
                        key={name}
                        className="category"
                        href={BASE_URL + `/oc-${name.replace(/ /g, '+')}`}
                      >
                        {name}
                      </a>
                    );
                  })}
                </Table.Cell>
                <Table.Cell>{record.score.toFixed(1)}</Table.Cell>
                <Table.Cell>{record.hits}</Table.Cell>
                <Table.Cell>{record.age}</Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>
      </Table>
    );
  }
}

class Categories extends React.PureComponent {
  render() {
    const { summedCategoryScores } = this.props;

    return (
      <div>
        <Header as="h2">Categories</Header>
        <Table celled>
          <Table.Header>
            <Table.Row>
              <Table.HeaderCell>Name</Table.HeaderCell>
              <Table.HeaderCell>Count</Table.HeaderCell>
              <Table.HeaderCell>Sum</Table.HeaderCell>
              <Table.HeaderCell>Average</Table.HeaderCell>
              <Table.HeaderCell>Median</Table.HeaderCell>
            </Table.Row>
          </Table.Header>

          <Table.Body>
            {summedCategoryScores.map(each => {
              return (
                <Table.Row key={each.name}>
                  <Table.Cell>
                    <a
                      href={BASE_URL + `/oc-${each.name.replace(/ /g, '+')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={`Filter by the '${each.name}' category`}
                    >
                      {each.name}
                    </a>
                  </Table.Cell>
                  <Table.Cell>{each.count}</Table.Cell>
                  <Table.Cell>{each.sum.toFixed(2)}</Table.Cell>
                  <Table.Cell>{each.avg.toFixed(2)}</Table.Cell>
                  <Table.Cell>{each.med.toFixed(2)}</Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table>
      </div>
    );
  }
}
