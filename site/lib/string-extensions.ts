declare global {
  interface String {
    toTitleCase(): string;
  }
}

String.prototype.toTitleCase = function (this: string): string {
  return this.charAt(0).toUpperCase() + this.slice(1).toLowerCase();
};

export {};
