export const sendMessage = (command: string, data: any) => {
  tsvscode.postMessage({
    command: command,
    data: data,
  });
};
