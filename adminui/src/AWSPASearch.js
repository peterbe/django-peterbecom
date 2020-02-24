import React from 'react';
import {
  Button,
  Input,
  Container,
  Header,
  Label,
  Loader,
  Select,
  Segment,
  Divider,
  Table
} from 'semantic-ui-react';
import { Link } from 'react-router-dom';
import { DisplayDate, filterToQueryString, ShowServerError } from './Common';

function getDefaultFilters(props) {
  const filters = { searchindex: 'Books' };
  const { location } = props;
  if (location.search) {
    const searchParams = new URLSearchParams(
      location.search.slice(1, location.search.length)
    );
    for (const [key, value] of searchParams) {
      filters[key] = value;
    }
  }
  return filters;
}

class AWSPASearch extends React.Component {
  state = {
    loading: false,
    data: null,
    serverError: null,
    filters: getDefaultFilters(this.props),
    allPossibleKeywords: null
  };

  componentDidMount() {
    document.title = 'Search AWS Affiliate Products';

    const { filters } = this.state;
    if (filters.keyword && filters.searchindex) {
      this.fetch();
    } else {
      this.fetchKeywords();
    }
  }

  fetch = async () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      let response;

      const overrides = {};
      const filters = Object.assign({}, this.state.filters);
      let url = '/api/v0/awspa/search';
      url += `?${filterToQueryString(filters, overrides)}`;
      try {
        response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${this.props.accessToken}`
          }
        });
      } catch (ex) {
        return this.setState({ loading: false, serverError: ex });
      }
      this.setState({ loading: false });
      if (response.ok) {
        const data = await response.json();
        this.setState({ data, serverError: null });
      } else {
        this.setState({ serverError: response });
      }
    });
  };

  fetchKeywords = async () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      let response;
      let url = '/api/v0/awspa/search/keywords';
      try {
        response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${this.props.accessToken}`
          }
        });
      } catch (ex) {
        return this.setState({ loading: false, serverError: ex });
      }
      this.setState({ loading: false });
      if (response.ok) {
        const data = await response.json();
        let allPossibleKeywords = data.all_possible_keywords;
        this.setState({ allPossibleKeywords, serverError: null });
      } else {
        this.setState({ serverError: response });
      }
    });
  };

  updateFilters = update => {
    if (update === null) {
      // Reset!
      this.setState({ filters: {} }, this.updateUrlThenFetch);
    } else {
      const clone = Object.assign({}, this.state.filters);
      const filters = Object.assign(clone, update);
      this.setState({ filters }, this.updateUrlThenFetch);
    }
  };

  updateUrlThenFetch = () => {
    let newURL = new URL(this.props.location.pathname, document.location.href);
    Object.entries(this.state.filters).forEach(([key, value]) => {
      if (value) newURL.searchParams.set(key, value);
    });
    this.props.history.push(newURL.pathname + newURL.search);
    if (this.state.filters.keyword && this.state.filters.searchindex) {
      this.fetch();
    }
  };

  removeProduct = product => {
    let data = Object.assign({}, this.state.data);
    data.products = data.products.filter(p => p.asin !== product.asin);
    this.setState({ data }, async () => {
      const formData = new FormData();
      formData.append('remove', product.asin);
      await fetch('/api/v0/awspa/search', {
        method: 'POST',
        body: formData,
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
    });
  };

  saveProduct = product => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      let response;
      const formData = new FormData();
      formData.append('asin', product.asin);
      formData.append('keyword', this.state.filters.keyword);
      formData.append('searchindex', this.state.filters.searchindex);
      try {
        response = await fetch('/api/v0/awspa/search', {
          method: 'POST',
          body: formData,
          headers: {
            Authorization: `Bearer ${this.props.accessToken}`
          }
        });
      } catch (ex) {
        return this.setState({ loading: false, serverError: ex });
      }
      if (response.ok) {
        this.setState({ serverError: null }, this.fetch);
      } else {
        this.setState({ serverError: response, loading: false });
      }
    });
  };

  render() {
    const {
      loading,
      data,
      filters,
      serverError,
      allPossibleKeywords
    } = this.state;
    const loadingStyle = {};
    if (loading && !data) {
      loadingStyle.margin = '200px 0';
    }

    return (
      <Container>
        <ShowServerError error={serverError} />
        {data && (
          <Header as="h1">
            AWS Affiliate Products Search Results
            {loading && <Loader active inline />}
          </Header>
        )}
        <Search filters={filters} updateFilters={this.updateFilters} />
        {loading && !data && (
          <Loader
            active
            content="Searching..."
            inline="centered"
            size="massive"
            style={loadingStyle}
          />
        )}

        {data && data.products && !!data.products.length && <Divider />}
        {data && data.products && (
          <ShowProducts
            products={data.products}
            saveProduct={this.saveProduct}
            removeProduct={this.removeProduct}
          />
        )}
        {allPossibleKeywords && (
          <ShowAllPossibleKeywords
            keywords={allPossibleKeywords}
            search={keyword => {
              this.updateFilters({ keyword });
            }}
          />
        )}
      </Container>
    );
  }
}

export default AWSPASearch;

function ShowAllPossibleKeywords({ keywords, search }) {
  return (
    <Table>
      <Table.Body>
        {keywords.map(keyword => {
          let sp = new URLSearchParams();
          sp.set('keyword', keyword.keyword);
          let uri = document.location.pathname + '?' + sp.toString();
          return (
            <Table.Row key={keyword.keyword}>
              <Table.Cell>
                <Link
                  to={uri}
                  onClick={() => {
                    search(keyword.keyword);
                  }}
                >
                  {keyword.keyword}
                </Link>
              </Table.Cell>
              <Table.Cell>{keyword.products}</Table.Cell>
            </Table.Row>
          );
        })}
      </Table.Body>
    </Table>
  );
}

function Search({
  filters,
  updateFilters,
  allSearchindexes,
  allKeywords,
  ...props
}) {
  const [keyword, setKeyword] = React.useState(filters.keyword || '');
  function submitHandler(event) {
    event.preventDefault();
    updateFilters({ keyword });
  }
  return (
    <form onSubmit={submitHandler}>
      <Segment>
        <Input
          fluid
          icon="search"
          placeholder="Keyword"
          value={keyword}
          onChange={(event, data) => {
            setKeyword(data.value);
          }}
        />
        <Select
          value={filters.searchindex}
          placeholder="Searchindex"
          options={[
            {
              key: 'Books',
              value: 'Books',
              text: `Books`
            },
            {
              key: 'All',
              value: 'All',
              text: `All`
            }
          ]}
          onChange={(event, data) => {
            updateFilters({ searchindex: data.value });
          }}
        />{' '}
        <Button type="submit" primary>
          Search
        </Button>
      </Segment>
    </form>
  );
}
function ShowProducts({
  products,
  toggleDisable,
  deleteProduct,
  saveProduct,
  removeProduct,
  ...props
}) {
  return (
    <div className="ui divided items">
      {products.map(product => {
        const style = {};
        if (product.disabled) {
          style.opacity = 0.35;
        }
        let preview;
        if (product.html) {
          preview = (
            <div
              key={product.id}
              style={style}
              className="item"
              dangerouslySetInnerHTML={{ __html: product.html }}
            />
          );
        } else {
          preview = (
            <div key={product.id} style={style}>
              <Header as="h4" style={{ color: 'red' }}>
                Preview Error!
              </Header>
              <pre>{product.html_error}</pre>
            </div>
          );
        }
        return [
          preview,
          <div key={`${product.id}:buttons`} style={{ marginBottom: 20 }}>
            {product.new ? (
              <span>
                <Label color="green">NEW!</Label>{' '}
                <Button onClick={event => saveProduct(product)} type="button">
                  Save
                </Button>
                <Button onClick={event => removeProduct(product)} type="button">
                  Remove
                </Button>
              </span>
            ) : (
              <span>
                {product.updated && <Label color="green">Updated!</Label>}{' '}
                <Button
                  onClick={event => toggleDisable(product.id)}
                  type="button"
                >
                  {product.disabled ? 'Enable' : 'Disable'}
                </Button>{' '}
                <Button
                  onClick={event => deleteProduct(product.id)}
                  type="button"
                >
                  Delete
                </Button>
                <br />
                {product.new ? (
                  <b>New!</b>
                ) : (
                  <span>
                    <b>Added:</b> <DisplayDate date={product.add_date} />{' '}
                    <b>Modified:</b> <DisplayDate date={product.modify_date} />{' '}
                    <b>ASIN:</b>{' '}
                    <Link to={`/awspa/${product.id}`}>{product.asin}</Link>{' '}
                  </span>
                )}
                <b>Keywords:</b>
                {product.keywords.map(kw => (
                  <code key={kw} style={{ marginRight: 5 }}>
                    {kw}
                  </code>
                ))}{' '}
                <b>Searchindex:</b> <code>{product.searchindex}</code>
              </span>
            )}
          </div>
        ];
      })}
    </div>
  );
}
