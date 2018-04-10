import React from 'react';
import { observer } from 'mobx-react';
import { Header } from 'semantic-ui-react';
// import { Link } from 'react-router-dom';
import {
  Button,
  Dimmer,
  Container,
  Loader,
  Input,
  Form,
  Checkbox,
  TextArea,
  Select,
} from 'semantic-ui-react';
// import { DisplayDate } from './Common';
import store from './Store';

export default observer(
  class EditDashboard extends React.Component {
    componentDidMount() {
      store.fetchBlogitem(this.props.match.params.id);
      store.fetchAllCategories();
    }
    render() {
      return (
        <Container>
          <Header as="h1">Edit</Header>
          {!store.blogitem ? (
            <Dimmer active inverted>
              <Loader size="massive">Loading</Loader>
            </Dimmer>
          ) : (
            <EditForm
              blogitem={store.blogitem}
              allCategories={store.allCategories}
            />
          )}
        </Container>
      );
    }
  }
);

class EditForm extends React.PureComponent {
  state = {
    hideLabels: JSON.parse(localStorage.getItem('hideLabels') || 'false'),
  };

  submitForm = event => {
    event.preventDefault();
    const data = {};
    const simpleKeys = ['oid', 'title', 'url', 'pub_date'];
    simpleKeys.forEach(key => {
      data[key] = this.refs[key].inputRef.value;
    });
    data.text = this.refs.text.ref.value;
    data.summary = this.refs.summary.ref.value;

    if (this.categories) {
      data.categories = this.categories;
    } else {
      data.categories = this.props.blogitem.categories.map(c => c.id);
    }
    data.keywords = this.refs.keywords.ref.value.trim().split(/\s*[\r\n]+\s*/g);
    console.log('DATA', data);
  };
  render() {
    const { blogitem, allCategories } = this.props;
    const hideLabels = this.state.hideLabels;

    const categoryOptions = allCategories.map(cat => ({
      key: cat.id,
      text: `${cat.name} (${cat.count})`,
      name: cat.name,
      value: cat.id,
    }));
    // console.log('blogitem.keywords', blogitem.keywords.length);
    const keywords = blogitem.keywords.map(keyword => keyword);
    // console.log('keywords', keywords);
    const categories = blogitem.categories.map(category => category.id);
    return (
      <Form onSubmit={this.submitForm}>
        <p style={{ textAlign: 'right' }}>
          <Button
            size="tiny"
            onClick={event => {
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
        </p>
        <Form.Field>
          {!hideLabels ? <label>OID</label> : null}
          <Input ref="oid" defaultValue={blogitem.oid} />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Title</label> : null}
          <Input ref="title" defaultValue={blogitem.title} />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Text</label> : null}
          <TextArea
            ref="text"
            rows={25}
            defaultValue={blogitem.text}
            style={{ overscrollBehaviorY: 'contain' }}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Summary</label> : null}
          <TextArea
            ref="summary"
            placeholder="Summary"
            rows={4}
            defaultValue={blogitem.summary}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>URL</label> : null}
          <Input
            ref="url"
            placeholder="URL"
            defaultValue={blogitem.url || ''}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Pub Date</label> : null}
          <Input
            ref="pub_date"
            placeholder="Pub date"
            defaultValue={blogitem.pub_date}
          />
        </Form.Field>
        <Form.Field>
          {!hideLabels ? <label>Categories</label> : null}
          <Select
            options={categoryOptions}
            selection
            multiple
            onChange={(event, data) => {
              this.categories = data.value;
              // console.log('DATA:', data);
            }}
            renderLabel={item => item.name}
            defaultValue={categories}
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
        <Form.Field>
          <Checkbox label="I agree to the Terms and Conditions" />
        </Form.Field>
        <Button type="submit">Save Changes</Button>
      </Form>
    );
  }
}
