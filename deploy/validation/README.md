# Current-build Kubernetes validation

This deploys the foundation test suite as an ephemeral Job. It does not start
the Orchestrator, expose an API or claim a production evaluation is available.
The application still needs authenticated runtime, role workflows and compatible
CSI block-backed ReadWriteOncePod storage before deployment.

The Job uses an immutable Harbor image digest, restricted Pod Security, non-root
UID, read-only root/test/config files, no service-account token and default-deny
ingress/egress. Only scratch is writable. Image pulls are performed by the node,
using a namespace-scoped `harbor-pull-secret` provisioned separately; never put
registry credentials in generated manifests or Git.

```sh
python deploy/validation/render.py \
  --image harbor.mlinarik.com/mlinarik/foundry-v2@sha256:<pushed-manifest-digest> \
  --revision <source-commit> > validation.yaml
kubectl apply --dry-run=client -f validation.yaml
```

After the operator selects this validation deployment, apply its namespace/policy,
provision the pull secret, server-dry-run the complete manifest and apply the Job.
Inspect its Completed condition and logs. Capture results before deleting validation
resources. A successful ephemeral Job verifies package/runtime behavior on the cluster;
it does not verify persistent-volume fencing, production sandbox root probes or live-model quality.
