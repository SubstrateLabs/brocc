import useSWR from "swr";
import { fetchConnections } from "../dashboard/actions";

export function useConnections(userId: string) {
  const { data, error, isLoading, mutate } = useSWR(userId ? `connections/${userId}` : null, () =>
    fetchConnections(userId),
  );

  return {
    connections: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}
