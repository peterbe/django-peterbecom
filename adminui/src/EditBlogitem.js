import React from 'react';
import { observer } from 'mobx-react';
import {
  Button,
  Message,
  Container,
  Loader,
  Input,
  Form,
  Checkbox,
  TextArea,
  Select
} from 'semantic-ui-react';
import { DisplayDate, Breadcrumbs } from './Common';
import store from './Store';

export default observer(
  class EditDashboard extends React.Component {
    // state = {
    //   id: null
    // };
    componentDidMount() {
      document.title = 'Edit blog post';

      if (store.blogitems.updated) {
        store.blogitems.setUpdated(null);
      }
      // console.log('MOUNT', this.props.match.params.id);
      store.blogitems.fetchBlogitem(this.props.match.params.id);
      if (!store.blogitems.allCategories.size) {
        store.blogitems.fetchAllCategories(store.user.accessToken);
      }
    }

    // static getDerivedStateFromProps(props, state) {
    //   console.log('DERIVED', props);
    //   console.log('COMPARE', props.match.params.id, state.id);
    //   if (props.match.params.id !== state.id) {
    //     store.blogitems.fetchBlogitem(
    //       props.match.params.id,
    //       store.user.accessToken
    //     );
    //     store.blogitems.fetchAllCategories(store.user.accessToken);
    //     return { state: props.match.params.id };
    //   }
    //   return null;
    // }

    // componentDidUpdate(prevProps) {
    //   console.log(
    //     'prevProps',
    //     prevProps.match.params.id,
    //     'Current',
    //     this.props.match.params.id
    //   );
    //   //   if (store.user.accessToken) {
    //   //     if (!store.blogitems.blogitem) {
    //   //       store.blogitems.fetchBlogitem(
    //   //         this.props.match.params.id,
    //   //         store.user.accessToken
    //   //       );
    //   //       store.blogitems.fetchAllCategories(store.user.accessToken);
    //   //     }
    //   //   }
    // }

    render() {
      // Using store.user.accessToken forces mobx to re-render which
      // will trigger componentDidUpdate()
      // if (!store.user.accessToken) {
      //   return null;
      // }
      // console.log('RENDER ID', this.props.match.params.id);
      // store.blogitems.fetchBlogitem(
      //   this.props.match.params.id,
      //   store.user.accessToken
      // );
      // store.blogitems.fetchAllCategories(store.user.accessToken);

      // console.log('RENDER ID', this.props.match.params.id);
      if (!store.blogitems.blogitem) {
        return null;
      }
      // console.log('RENDER', store.blogitems.blogitem.title);
      return (
        <Container>
          <Breadcrumbs
            tos={[{ to: '/blogitems', name: 'Blogitems' }]}
            active="Edit Blog Post"
          />

          {store.blogitems.serverError ? (
            <Message negative>
              <Message.Header>Server Error</Message.Header>
              <p>
                <code>{store.blogitems.serverError}</code>
              </p>
            </Message>
          ) : null}

          {store.blogitems.updated ? (
            <Message
              positive
              onDismiss={() => {
                store.blogitems.setUpdated(null);
              }}
            >
              <Message.Header>Updated</Message.Header>
              <p>
                <b>
                  <DisplayDate date={store.blogitems.updated} />
                </b>
              </p>
            </Message>
          ) : null}

          {!store.blogitems.loaded ? <Loader active inline="centered" /> : null}

          {store.blogitems.loaded && !store.blogitems.serverError ? (
            <EditForm
              blogitem={store.blogitems.blogitem}
              allCategories={store.blogitems.allCategories}
              accessToken={store.user.accessToken}
            />
          ) : null}
        </Container>
      );
    }
  }
);

class EditForm extends React.PureComponent {
  state = {
    hideLabels: JSON.parse(localStorage.getItem('hideLabels') || 'false'),
    showUnimportantFields: false,
    saving: false
  };

  componentDidMount() {
    this.setRefs(this.props.blogitem);
  }

  componentDidUpdate(prevProps) {
    if (prevProps.blogitem !== this.props.blogitem) {
      this.setRefs(this.props.blogitem);
    }
  }
  setRefs = blogitem => {
    console.log('setRefs', blogitem.title);
    const simpleKeys = ['oid', 'title', 'url', 'pub_date'];
    simpleKeys.forEach(key => {
      this.refs[key].inputRef.value = blogitem[key];
    });
    this.refs.text.ref.value = blogitem.text;
    this.refs.summary.ref.value = blogitem.summary;
    const categories = blogitem.categories.map(category => category.id);
    this.categories = categories;
    this.refs.keywords.ref.value = blogitem.keywords.join('\n');
  };

  submitForm = event => {
    event.preventDefault();
    const { blogitem } = this.props;
    const data = {};
    // data.title = this.state.title;
    // const simpleKeys = ['oid', 'title', 'url', 'pub_date'];
    const simpleKeys = ['oid', 'title', 'url', 'pub_date'];
    simpleKeys.forEach(key => {
      data[key] = this.refs[key].inputRef.value;
    });
    data.text = this.refs.text.ref.value;
    data.summary = this.refs.summary.ref.value;

    if (this.categories) {
      data.categories = this.categories;
    } else {
      data.categories = blogitem.categories.map(c => c.id);
    }
    data.keywords = this.refs.keywords.ref.value.trim().split(/\s*[\r\n]+\s*/g);
    data.display_format = this.displayFormat
      ? this.displayFormat.value
      : blogitem.display_format;
    data.codesyntax = this.codesyntax
      ? this.codesyntax.value
      : blogitem.codesyntax;
    data.disallow_comments = this.disallowComments
      ? this.disallowComments.checked
      : blogitem.disallow_comments;
    data.hide_comments = this.hideComments
      ? this.hideComments.checked
      : blogitem.hide_comments;

    store.blogitems.setUpdated(null);
    store.blogitems.updateBlogitem(blogitem.id, data, this.props.accessToken);
  };
  render() {
    // console.log('RENDER EditForm', this.props.blogitem.title);
    const { blogitem, allCategories } = this.props;
    const { hideLabels, showUnimportantFields } = this.state;

    const categoryOptions = allCategories.map(cat => ({
      key: cat.id,
      text: `${cat.name} (${cat.count})`,
      name: cat.name,
      value: cat.id
    }));
    // console.log('blogitem.keywords', blogitem.keywords.length);
    const keywords = blogitem.keywords.map(keyword => keyword);
    // console.log('keywords', keywords);
    // const categories = blogitem.categories.map(category => category.id);
    this.categories = blogitem.categories.map(category => category.id);
    const displayFormat = blogitem.display_format;
    const displayFormatOptions = ['markdown', 'structuredtext'].map(o => {
      return { key: o, text: o, name: o, value: o };
    });
    return (
      <Form onSubmit={this.submitForm}>
        <h3>{blogitem.title}</h3>
        <p style={{ textAlign: 'right' }}>
          <Button
            size="mini"
            secondary={!this.state.hideLabels}
            onClick={event => {
              event.preventDefault();
              this.setState({ hideLabels: !this.state.hideLabels }, () => {
                localStorage.setItem(
                  'hideLabels',
                  JSON.stringify(this.state.hideLabels)
                );
              });
            }}
          >
            {hideLabels ? 'Show labels' : 'Hide labels'}
          </Button>
          <Button
            size="mini"
            secondary={showUnimportantFields}
            onClick={event => {
              event.preventDefault();
              this.setState({
                showUnimportantFields: !showUnimportantFields
              });
            }}
          >
            {showUnimportantFields ? 'Hide some fields' : 'Show all fields'}
          </Button>
        </p>
        <Form.Field>
          {!hideLabels ? <label>OID</label> : null}
          <Input ref="oid" />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Title</label> : null}
          <Input ref="title" />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Text</label> : null}
          <TextArea
            ref="text"
            rows={25}
            style={{ overscrollBehaviorY: 'contain' }}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Summary</label> : null}
          <TextArea ref="summary" rows={4} />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>URL</label> : null}
          <Input ref="url" placeholder="URL" />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Pub Date</label> : null}
          <Input ref="pub_date" placeholder="Pub date" />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Categories</label> : null}
          <Select
            value={this.categories}
            options={categoryOptions}
            selection
            multiple
            onChange={(event, data) => {
              this.categories = data.value;
              console.log('DATA:', data);
              console.log('DATA.value:', data.value);
            }}
            renderLabel={item => item.name}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Keywords</label> : null}
          <TextArea
            ref="keywords"
            placeholder="Keywords"
            rows={5}
            defaultValue={keywords.join('\n')}
          />
        </Form.Field>
        {showUnimportantFields ? (
          <Form.Field>
            {!hideLabels ? <label>Display Format</label> : null}
            <Select
              options={displayFormatOptions}
              selection
              onChange={(event, data) => {
                this.displayFormat = data;
                // console.log('DATA:', data);
              }}
              renderLabel={item => item.name}
              defaultValue={displayFormat}
            />
          </Form.Field>
        ) : null}
        {showUnimportantFields ? (
          <Form.Field>
            {!hideLabels ? <label>Code Syntax</label> : null}
            <Input
              placeholder="Code Syntax"
              onChange={(event, data) => {
                this.codesyntax = data;
              }}
              defaultValue={blogitem.codesyntax}
            />
          </Form.Field>
        ) : null}
        {showUnimportantFields ? (
          <Form.Field>
            <Checkbox
              label="Disallow comments"
              ref="disallow_comments"
              onChange={(event, data) => {
                this.disallowComments = data;
              }}
              defaultChecked={!!blogitem.disallow_comments}
            />
          </Form.Field>
        ) : null}
        {showUnimportantFields ? (
          <Form.Field>
            <Checkbox
              label="Hide comments"
              ref="hide_comments"
              onChange={(event, data) => {
                this.hideComments = data;
              }}
              defaultChecked={!!blogitem.hide_comments}
            />
          </Form.Field>
        ) : null}
        <Button
          type="submit"
          primary={true}
          loading={this.state.saving}
          onClick={() => {
            this.setState({ saving: true }, () => {
              window.setTimeout(() => {
                if (!this.dismounted) {
                  this.setState({ saving: false });
                }
              }, 2000);
            });
          }}
        >
          Save Changes
        </Button>
      </Form>
    );
  }
}
