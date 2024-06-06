coq
Theorem evensum_even : forall (n m:nat), Even n -> Even m -> Even (n+m).
Proof.
  intros n m H1 H2.
  destruct (Even (n+m)) as [Even_nm | _].
  - simpl in *.
    reflexivity.
  - discriminate.
Qed.