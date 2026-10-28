# PARCS [Python]

## Recommended testing workflow

When developing a parallel PARCS solution, test it progressively before using
paid cloud resources:

1. **Implement the parallel algorithm.**
   Create a solution that distributes work between workers and combines the
   received results.

2. **Test on one machine first.**
   Run the master and several workers as Docker containers on the same machine.
   This is the fastest and cheapest way to find implementation, scheduling, and
   basic networking issues.

   See [Same-machine test guide](guide_run_on_same_machine.md).

3. **Optionally test in a local network.**
   Run the master and workers on separate machines in the same LAN. This
   validates node registration and HTTP/Pyro5 communication through real network
   addresses before deploying to a cloud provider.

   See [Local-network test guide](guide_run_in_local_network.md).

4. **Test in Google Cloud.**
   Create master and worker Compute Engine instances only after local testing is
   successful. Google Cloud resources may incur charges, so delete the test VMs,
   disks, and temporary firewall rules after completing the test.

   See [Google Cloud test guide](guide_run_on_google_cloud.md).

Following this order reduces debugging time and helps avoid unnecessary cloud
costs.
