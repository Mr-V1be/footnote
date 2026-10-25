import { describe, expect, it } from "vitest";

import en from "../../../messages/en.json";
import ru from "../../../messages/ru.json";

type Catalogue = { [key: string]: string | Catalogue };

/** Every message of a catalogue by its dotted key. */
function flatten(catalogue: Catalogue, prefix = ""): Map<string, string> {
  const messages = new Map<string, string>();
  for (const [key, value] of Object.entries(catalogue)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") messages.set(path, value);
    else for (const entry of flatten(value, path)) messages.set(...entry);
  }
  return messages;
}

/**
 * Names of the arguments an ICU message takes, nested ones included:
 * "{count, plural, one {# of {total}}}" takes count and total. Literal text
 * of the sub-messages is skipped, whatever the language.
 */
function argumentsOf(message: string): Set<string> {
  const names = new Set<string>();
  let index = 0;
  const readText = (): void => {
    while (index < message.length && message[index] !== "}") {
      if (message[index] === "{") readArgument();
      else index += 1;
    }
  };
  const readArgument = (): void => {
    index += 1;
    const close = message.slice(index).search(/[,}]/);
    names.add(message.slice(index, index + close).trim());
    index += close;
    if (message[index] === ",") {
      const type = message.slice(index + 1).match(/^\s*(\w+)\s*(,?)/);
      index += 1 + (type?.[0].length ?? 0);
      if (type?.[2]) {
        // plural / select: "key {sub-message}" pairs up to the closing brace.
        while (index < message.length && message[index] !== "}") {
          if (message[index] === "{") {
            index += 1;
            readText();
          }
          index += 1;
        }
      }
    }
    index += 1;
  };
  readText();
  return names;
}

describe("message catalogues", () => {
  const source = flatten(ru);
  const english = flatten(en);

  it("are compared by the arguments their messages take", () => {
    const margin = source.get("checks.detail.margin") ?? "";
    expect([...argumentsOf(margin)].sort()).toEqual(["measured", "min", "side", "value"]);
    const total = english.get("checks.detail.font_size_widespread") ?? "";
    expect([...argumentsOf(total)].sort()).toEqual(["count", "size", "total"]);
  });

  it("have the same keys in every language", () => {
    expect([...english.keys()].sort()).toEqual([...source.keys()].sort());
  });

  it("take the same arguments in every language", () => {
    for (const [key, message] of source) {
      expect([...argumentsOf(english.get(key) ?? "")].sort(), key).toEqual(
        [...argumentsOf(message)].sort(),
      );
    }
  });
});
