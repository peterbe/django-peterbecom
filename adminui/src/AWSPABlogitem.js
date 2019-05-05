import React from 'react';
import {
  Button,
  Container,
  Header,
  Label,
  Loader,
  Message,
  Segment,
  Select
} from 'semantic-ui-react';

import { BlogitemBreadcrumb, DisplayDate, ShowServerError } from './Common';

class AWSPABlogitem extends React.Component {
  state = {
    loading: true,
    products: null,
    serverError: null,
    updated: null
  };

  componentDidMount() {
    document.title = 'AWSPA';
    this.fetchPossibleProducts();
  }

  fetchPossibleProducts = async () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    const oid = this.props.match.params.oid;
    let response;
    try {
      response = await fetch(`/api/v0/plog/${oid}/awspa`, {
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
      this.setState({ products: data.products, serverError: null });
    } else {
      this.setState({ serverError: response });
    }
  };

  toggleDisable = async id => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    const oid = this.props.match.params.oid;
    let response;
    const formData = new FormData();
    formData.append('id', id);
    try {
      response = await fetch(`/api/v0/plog/${oid}/awspa`, {
        method: 'POST',
        body: formData,
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
      this.setState({ products: data.products, serverError: null });
    } else {
      this.setState({ serverError: response });
    }
  };

  deleteProduct = async id => {
    if (window.confirm('Are you sure?')) {
      if (!this.props.accessToken) {
        throw new Error('No accessToken');
      }
      const oid = this.props.match.params.oid;
      let response;
      try {
        response = await fetch(`/api/v0/plog/${oid}/awspa?id=${id}`, {
          method: 'DELETE',
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
        this.setState({ products: data.products, serverError: null });
      } else {
        this.setState({ serverError: response });
      }
    }
  };

  searchMore = async (keyword, searchindex) => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    const oid = this.props.match.params.oid;
    let response;
    const formData = new FormData();
    formData.append('keyword', keyword);
    formData.append('searchindex', searchindex);
    try {
      response = await fetch(`/api/v0/plog/${oid}/awspa`, {
        method: 'POST',
        body: formData,
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
      this.setState({ products: data.products, serverError: null });
    } else {
      this.setState({ serverError: response });
    }
  };

  render() {
    const { loading, products, serverError } = this.state;
    const oid = this.props.match.params.oid;
    if (!serverError && loading) {
      return (
        <Container>
          <Loader
            active
            content="Loading Images..."
            inline="centered"
            size="massive"
            style={{ margin: '200px 0' }}
          />
        </Container>
      );
    }
    return (
      <Container>
        <BlogitemBreadcrumb oid={oid} page="awspa" />
        <ShowServerError error={this.state.serverError} />
        <Header as="h1">AWS Affiliate Products</Header>
        {products && (
          <div className="all-keywords">
            {Object.entries(products).map(([keyword, products]) => (
              <ShowKeywordProduct
                deleteProduct={this.deleteProduct}
                key={keyword}
                keyword={keyword}
                products={products}
                searchMore={this.searchMore}
                toggleDisable={this.toggleDisable}
              />
            ))}
          </div>
        )}
      </Container>
    );
  }
}

export default AWSPABlogitem;

function ShowKeywordProduct({
  deleteProduct,
  keyword,
  products,
  searchMore,
  toggleDisable
}) {
  const [searchindex, setSearchindex] = React.useState('Books');
  const [searching, setSearching] = React.useState(false);
  React.useEffect(() => {
    if (searching) setSearching(false);
  }, [products, searching]);
  const searchIndexOptions = [
    { key: 'Books', text: 'Books', value: 'Books' },
    { key: 'All', text: 'All', value: 'All' }
  ];
  const newProducts = products.filter(p => p._new);
  return (
    <Segment>
      {newProducts.length ? (
        <Message positive>
          <Message.Header>({newProducts.length}) New products</Message.Header>
          <ol>
            {newProducts.map(p => (
              <li key={p.id}>
                <b>{p.title}</b>
              </li>
            ))}
          </ol>
        </Message>
      ) : null}
      <div className="loadmore" style={{ float: 'right' }}>
        <Select
          onChange={(event, data) => setSearchindex(data.value)}
          options={searchIndexOptions}
          value={searchindex}
        />{' '}
        <Button
          loading={searching}
          onClick={event => {
            setSearching(true);
            searchMore(keyword, searchindex);
          }}
          type="button"
        >
          Search more
        </Button>
      </div>
      <h2>{keyword}</h2>
      <div className="ui divided items">
        {products.map(product => {
          const style = {};
          if (product.disabled) {
            style.opacity = 0.35;
          }
          return [
            <div
              className="item"
              dangerouslySetInnerHTML={{ __html: product.html }}
              key={product.id}
              style={style}
            />,
            <div key={product.id + 'buttons'} style={{ marginBottom: 20 }}>
              {product._new && (
                <Label color="green">
                  <span role="img" aria-label="New!">
                    🔥
                  </span>{' '}
                  New!{' '}
                  <span role="img" aria-label="New!">
                    🔥
                  </span>
                </Label>
              )}{' '}
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
              <b>Added:</b> <DisplayDate date={product.add_date} />{' '}
              <b>Modified:</b> <DisplayDate date={product.modify_date} />{' '}
            </div>
          ];
        })}
      </div>
    </Segment>
  );
}
