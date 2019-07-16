import { render } from "preact";
import "./style.css";
import App from "./app";

const root = document.getElementById("root");
const form = root.querySelector("form");
let initialValue = "";
let initialInput = form.querySelector('input[name="term"]');
if (initialInput) {
  initialValue = initialInput.value;
}
render(<App initialValue={initialValue} />, root, form);
