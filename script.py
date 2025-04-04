import boto3
import csv
from itertools import chain, combinations
from botocore.exceptions import ClientError

# Only A-series AMD instance types
AMD_A_SERIES_INSTANCES = ["m5a", "r5a", "c6a", "m6a", "t3a", "r6a", "hpc6a", "g4ad", "m7a", "c7a", "r7a"]

def get_all_regions():
    """Fetch available AWS regions where Spot instances are  supported."""
    ec2 = boto3.client('ec2', region_name='us-east-1')
    response = ec2.describe_regions(AllRegions=True)
    return [r['RegionName'] for r in response['Regions'] if r.get('OptInStatus', 'opted-in') != 'not-opted-in']

def get_filtered_instance_types(region, exact_vcpus, exact_memory_gib):
    """Fetch A-series AMD instance types matching exact vCPUs and RAM."""
    ec2 = boto3.client('ec2', region_name=region)
    filters = [
        {'Name': 'vcpu-info.default-vcpus', 'Values': [str(exact_vcpus)]},
        {'Name': 'memory-info.size-in-mib', 'Values': [str(int(exact_memory_gib * 1024))]},
        {'Name': 'supported-usage-class', 'Values': ['spot']}
    ]
    instance_types = []
    try:
        paginator = ec2.get_paginator('describe_instance_types')
        for page in paginator.paginate(Filters=filters):
            for it in page['InstanceTypes']:
                if any(it['InstanceType'].startswith(prefix) for prefix in AMD_A_SERIES_INSTANCES):
                    instance_types.append(it['InstanceType'])
    except ClientError as e:
        print(f"Error fetching instance types in region {region}: {e}")
    return instance_types

def get_spot_placement_scores(region, instance_type_list):
    """Retrieve Spot placement scores for a set of instance types."""
    ec2 = boto3.client('ec2', region_name=region)
    try:
        response = ec2.get_spot_placement_scores(
            InstanceTypes=instance_type_list,
            TargetCapacity=1,
            SingleAvailabilityZone=False,
            RegionNames=[region]
        )
    except ClientError as e:
        print(f"Error fetching spot placement scores in {region} for {instance_type_list}: {e}")
        return {}

    scores = {}
    for record in response.get('SpotPlacementScores', []):
        if 'InstanceTypes' in record:
            for itype in record['InstanceTypes']:
                score = record['Score']
                scores[itype] = max(scores.get(itype, 0), score)
    return scores

def powerset(iterable, min_size=3):
    """Generate all subsets of an iterable with at least `min_size` elements."""
    s = list(iterable)
    return [set(comb) for comb in chain.from_iterable(combinations(s, r) for r in range(min_size, len(s)+1))]

def main():
    exact_vcpus = int(input("Enter exact number of vCPUs: "))
    exact_memory = float(input("Enter exact memory (GiB): "))
    output_file = "highest_spot_placement_score.csv"

    region = "us-east-1"
    print(f"Processing region: {region}")

    # Step 1: Get filtered instance types
    instance_types = get_filtered_instance_types(region, exact_vcpus, exact_memory)
    if not instance_types:
        print(f"No matching AMD A-series instances found in {region}. Exiting.")
        return

    print(f"Filtered instance types: {instance_types}")

    # Step 2: Generate power set of instance types (only sets with 3+ elements)
    instance_combinations = powerset(instance_types)

    # Step 3: Calculate Spot placement scores for each subset
    best_set = None
    highest_score = 0
    results = []

    for subset in instance_combinations:
        subset_list = list(subset)
        scores = get_spot_placement_scores(region, subset_list)
        total_score = sum(scores.values())  # Sum of scores for this subset

        results.append({
            "instance_set": ', '.join(subset_list),
            "score": total_score
        })

        if total_score > highest_score:
            highest_score = total_score
            best_set = subset_list

    # Step 4: Save results to CSV
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = ["instance_set", "score"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Results saved to {output_file}")
    print(f"Best instance set: {best_set} with a Spot placement score of {highest_score}")

if __name__ == '__main__':
    main()
