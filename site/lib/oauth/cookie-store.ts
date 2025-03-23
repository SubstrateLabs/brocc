export abstract class CookieStore {
  constructor() {}

  abstract setEphemeral({
    name,
    value,
  }: {
    name: string;
    value: string;
  }): Promise<void>;

  abstract get(name: string): Promise<string | null>;

  abstract delete(name: string): Promise<void>;
}
