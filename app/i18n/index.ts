import de from "../../shared/strings/de.json";
import { render, type Params, type Strings } from "./t";

const strings = de as Strings;

export function t(key: string, params?: Params): string {
  return render(strings, key, params);
}
