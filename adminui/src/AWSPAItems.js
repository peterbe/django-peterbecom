import React from 'react';
import {
  Button,
  Input,
  Container,
  Header,
  Loader,
  Select,
  Pagination,
  Segment,
  Divider
} from 'semantic-ui-react';
import { Link } from 'react-router-dom';
import { DisplayDate, filterToQueryString, ShowServerError } from './Common';

function getDefaultFilters(props) {
  const filters = {};
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
class AWSPA extends React.Component {
  state = {
    loading: false,
    data: null,
    serverError: null,
    filters: getDefaultFilters(this.props),
    batchsize: JSON.parse(localStorage.getItem('awspa:batchsize') || '10'),
    page: 1,
    orderBy: localStorage.getItem('awspa:orderby') || '-add_date'
  };

  componentDidMount() {
    document.title = 'AWS Affiliate Products';
    this.fetch();
  }

  fetch = async () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      let response;

      const overrides = {
        batch_size: this.state.batchsize,
        page: this.state.page
      };
      const filters = Object.assign({}, this.state.filters);
      if (this.state.orderBy) {
        overrides.order_by = this.state.orderBy;
      }
      let url = '/api/v0/awspa';
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
    this.fetch();
  };

  refreshProduct = id => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      let response;
      const formData = new FormData();
      formData.append('refresh', true);
      try {
        response = await fetch(`/api/v0/awspa/${id}`, {
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

  deleteProduct = id => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      let response;
      try {
        response = await fetch(`/api/v0/awspa/${id}`, {
          method: 'DELETE',
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

  toggleDisable = id => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    this.setState({ loading: true }, async () => {
      let response;
      const formData = new FormData();
      formData.append('disable', true);
      try {
        response = await fetch(`/api/v0/awspa/${id}`, {
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
      batchsize,
      filters,
      serverError,
      page,
      orderBy
    } = this.state;
    const loadingStyle = {};
    if (loading && !data) {
      loadingStyle.margin = '200px 0';
    }

    return (
      <Container>
        {loading && !data && (
          <Loader
            active
            content="Loading AWSPA Items..."
            inline="centered"
            size="massive"
            style={loadingStyle}
          />
        )}

        <ShowServerError error={serverError} />
        {data && (
          <Header as="h1">
            AWS Affiliate Products ({data.count})
            {loading && <Loader active inline />}
          </Header>
        )}
        {data && (
          <ShowTable
            filters={filters}
            deleteProduct={this.deleteProduct}
            products={data.products}
            allKeywords={data.all_keywords}
            allSearchindexes={data.all_searchindexes}
            toggleDisable={this.toggleDisable}
            refreshProduct={this.refreshProduct}
            updateFilters={this.updateFilters}
          />
        )}
        <Divider />
        {data && (
          <Pagination
            boundaryRange={0}
            activePage={page}
            ellipsisItem={null}
            firstItem={null}
            lastItem={null}
            siblingRange={1}
            onPageChange={(e, { activePage }) => {
              this.setState({ page: activePage }, this.fetch);
            }}
            totalPages={Math.floor(data.count / this.state.batchsize)}
          />
        )}
        {data && (
          <Segment>
            Batch size{' '}
            <Select
              placeholder="Batch size"
              value={batchsize}
              options={[
                { key: 5, value: 5, text: 5 },
                { key: 10, value: 10, text: 10 },
                { key: 25, value: 25, text: 25 },
                { key: 100, value: 100, text: 100 }
              ]}
              onChange={(event, data) => {
                this.setState({ batchsize: data.value }, () => {
                  localStorage.setItem(
                    'awspa:batchsize',
                    JSON.stringify(this.state.batchsize)
                  );
                  this.fetch();
                });
              }}
            />{' '}
            Order by{' '}
            <Select
              placeholder="Order by"
              value={orderBy}
              options={[
                {
                  key: 'modify_date',
                  value: 'modify_date',
                  text: 'Modified (ascending)'
                },
                {
                  key: '-modify_date',
                  value: '-modify_date',
                  text: 'Modified (descending)'
                },
                {
                  key: 'add_date',
                  value: 'add_date',
                  text: 'Added (ascending)'
                },
                {
                  key: '-add_date',
                  value: '-add_date',
                  text: 'Added (descending)'
                }
              ]}
              onChange={(event, data) => {
                this.setState({ orderBy: data.value }, () => {
                  localStorage.setItem('awspa:orderby', this.state.orderBy);
                  this.fetch();
                });
              }}
            />
          </Segment>
        )}
      </Container>
    );
  }
}

export default AWSPA;

function ShowTable({
  filters,
  updateFilters,
  allSearchindexes,
  allKeywords,
  ...props
}) {
  const [title, setTitle] = React.useState(filters.title || '');
  function submitHandler(event) {
    updateFilters({ title });
    event.preventDefault();
  }

  return (
    <form onSubmit={submitHandler}>
      <Segment>
        <Input
          fluid
          icon="search"
          placeholder="ASIN or Title freetext search..."
          value={title}
          onChange={(event, data) => {
            setTitle(data.value);
          }}
        />
        <Select
          placeholder="Keyword"
          options={allKeywords.map(k => ({
            key: k.value,
            value: k.value,
            text: `${k.value} (${k.count})`
          }))}
          value={filters.keyword}
          onChange={(event, data) => {
            updateFilters({ keyword: data.value });
          }}
        />{' '}
        <Select
          value={filters.searchindex}
          placeholder="Searchindex"
          options={allSearchindexes.map(k => ({
            key: k.value,
            value: k.value,
            text: `${k.value} (${k.count})`
          }))}
          onChange={(event, data) => {
            updateFilters({ searchindex: data.value });
          }}
        />{' '}
        <Select
          value={filters.disabled || ''}
          placeholder="Disabled/Enabled"
          options={[
            { key: 'any', value: '', text: 'Any' },
            { key: 'disabled', value: 'yes', text: 'Disabled' },
            { key: 'enabled', value: 'no', text: 'Enabled' }
          ]}
          onChange={(event, data) => {
            if (data.value === undefined) {
              updateFilters({ disabled: null });
            } else {
              updateFilters({ disabled: data.value });
            }
          }}
        />{' '}
        <Select
          value={filters.converted || ''}
          placeholder="PAAPIv5"
          options={[
            { key: 'any', value: '', text: 'Any' },
            { key: 'notconverted', value: 'no', text: 'Not converted' },
            { key: 'converted', value: 'yes', text: 'Converted' }
          ]}
          onChange={(event, data) => {
            updateFilters({ converted: data.value });
          }}
        />{' '}
        <Select
          value={filters.hasoffers || ''}
          placeholder="Has offers"
          options={[
            { key: 'any', value: '', text: 'Any' },
            { key: 'has', value: 'no', text: 'No offers' },
            { key: 'hasnot', value: 'yes', text: 'Has offers' }
          ]}
          onChange={(event, data) => {
            updateFilters({ hasoffers: data.value });
          }}
        />{' '}
        <Button
          type="button"
          disabled={
            !(
              filters.title ||
              filters.keyword ||
              filters.searchindex ||
              filters.hasoffers ||
              filters.converted ||
              filters.disabled !== null
            )
          }
          onClick={event => {
            updateFilters(null);
          }}
        >
          Clear
        </Button>
      </Segment>
      <ShowProducts {...props} />
    </form>
  );
}
function ShowProducts({
  products,
  toggleDisable,
  deleteProduct,
  refreshProduct,
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
            <Button onClick={event => toggleDisable(product.id)} type="button">
              {product.disabled ? 'Enable' : 'Disable'}
            </Button>{' '}
            <Button onClick={event => deleteProduct(product.id)} type="button">
              Delete
            </Button>
            <Button onClick={event => refreshProduct(product.id)} type="button">
              Refresh
            </Button>
            <br />
            <b>Added:</b> <DisplayDate date={product.add_date} />{' '}
            <b>Modified:</b> <DisplayDate date={product.modify_date} />{' '}
            <b>PAAPIv5:</b>{' '}
            {product.paapiv5 ? (
              <span aria-label="check" role="img">
                ✅
              </span>
            ) : (
              <span aria-label="no" role="img">
                ❌
              </span>
            )}{' '}
            <b>ASIN:</b> <Link to={`/awspa/${product.id}`}>{product.asin}</Link>{' '}
            <b>Keyword:</b> <code>{product.keyword}</code> <b>Searchindex:</b>{' '}
            <code>{product.searchindex}</code>
          </div>
        ];
      })}
    </div>
  );
}
